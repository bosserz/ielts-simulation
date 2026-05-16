"""
Gemini API integration for Writing and Speaking scoring.

Writing band descriptors are loaded once at import time and reused across all
calls — never re-sent as raw string concatenation per call. This is the
closest analog to prompt caching for the Gemini API.
"""
import json
import re
import google.generativeai as genai
from flask import current_app


def _extract_json(raw: str) -> dict:
    """
    Extract the first JSON object from a Gemini response string.
    Handles markdown code fences, leading prose, and trailing text.
    """
    # Strip markdown fences: ```json ... ``` or ``` ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())

    # Fast path: try parsing directly
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Slow path: find the outermost { ... } block
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in Gemini response: {raw[:200]}")
    depth = 0
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start : i + 1])
    raise ValueError(f"Unterminated JSON object in Gemini response: {raw[:200]}")

_MODEL_WRITING = "gemini-2.5-flash"
_MODEL_SPEAKING_EXAMINER = "gemini-2.5-flash"
_MODEL_SPEAKING_SCORER = "gemini-2.5-flash"
# Report uses the latest Pro model via the modern google-genai SDK for
# higher-quality long-form coaching narrative.
_MODEL_REPORT = "gemini-2.5-pro"

# IELTS Writing Band Descriptors (abbreviated; replace with full official text)
_WRITING_BAND_DESCRIPTORS = """
IELTS Academic Writing Band Descriptors (Task 1 & Task 2)

Task Response (TR): Extent to which the candidate addresses all parts of the task, presents a clear position, supports ideas with relevant evidence and examples.
Coherence and Cohesion (CC): Logical organisation of information, use of cohesive devices, paragraphing.
Lexical Resource (LR): Range of vocabulary, accuracy of word choice and spelling, use of collocations.
Grammatical Range and Accuracy (GRA): Range of structures, frequency of grammatical errors, punctuation.

Bands run from 0 (did not attempt) to 9 (expert user).
Half-bands (e.g. 6.5) are awarded.
"""

_SPEAKING_BAND_DESCRIPTORS = """
IELTS Speaking Band Descriptors

Fluency and Coherence (FC): Ability to speak at length without noticeable effort, logical sequencing, appropriate use of discourse markers.
Lexical Resource (LR): Range and accuracy of vocabulary, use of paraphrase.
Grammatical Range and Accuracy (GRA): Range of structures, frequency of errors.
Pronunciation (P): Clarity of speech; note that accurate pronunciation assessment from text alone is limited — flag for teacher review.

Bands run from 0 to 9. Half-bands are awarded.
"""


def _client():
    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
    return genai


def score_writing(task_number: int, question_prompt: str, essay_text: str, exam_type: str = "ACADEMIC") -> dict:
    """
    Score a Writing Task 1 or Task 2 essay using Gemini.

    The essay is uploaded to the Gemini Files API as a text/plain file so the
    model reads it as a document rather than inline prompt text. The temporary
    file is deleted from Gemini storage after scoring.

    Returns a dict with keys:
        taskResponse, coherenceCohesion, lexicalResource, grammaticalRange,
        overallBand, feedback, sentenceHighlights
    """
    import io
    _client()
    model = genai.GenerativeModel(
        model_name=_MODEL_WRITING,
        system_instruction=(
            f"You are an expert IELTS examiner. Use the following official band descriptors:\n"
            f"{_WRITING_BAND_DESCRIPTORS}\n\n"
            "Return ONLY valid JSON with no markdown fencing."
        ),
    )

    # Upload the essay as a plain-text file to Gemini Files API
    uploaded_file = genai.upload_file(
        io.BytesIO(essay_text.encode("utf-8")),
        mime_type="text/plain",
        display_name=f"writing_task_{task_number}.txt",
    )

    task_label = f"Task {task_number} ({'Academic' if exam_type == 'ACADEMIC' else 'General Training'})"
    prompt = [
        f"Score this IELTS Writing {task_label} response.\n\n"
        f"Question prompt:\n{question_prompt}\n\n"
        "The student's essay is in the attached file.\n\n"
        "Return JSON matching this schema exactly:\n"
        "{\n"
        '  "taskResponse": <float 0-9>,\n'
        '  "coherenceCohesion": <float 0-9>,\n'
        '  "lexicalResource": <float 0-9>,\n'
        '  "grammaticalRange": <float 0-9>,\n'
        '  "overallBand": <float 0-9, average of above rounded to nearest 0.5>,\n'
        '  "feedback": "<2-3 paragraph narrative feedback>",\n'
        '  "sentenceHighlights": [\n'
        '    {"sentenceIndex": <int>, "complexity": "simple|compound|complex", "suggestion": "<string or null>"}\n'
        "  ]\n"
        "}",
        uploaded_file,
    ]

    try:
        response = model.generate_content(prompt)
        result = _extract_json(response.text)
        result["ai_model"] = _MODEL_WRITING
        return result
    finally:
        try:
            genai.delete_file(uploaded_file.name)
        except Exception:
            pass


def generate_speaking_followup(topic: str, transcript_summary: str, part_number: int = 3) -> list[str]:
    """
    Generate Part 3 follow-up questions from the student's Part 2 transcript.
    Returns a list of 3 question strings.
    """
    _client()
    model = genai.GenerativeModel(
        model_name=_MODEL_SPEAKING_EXAMINER,
        system_instruction="You are an IELTS examiner conducting a Speaking test. Return ONLY valid JSON.",
    )

    prompt = (
        f"The student just completed IELTS Speaking Part 2 on the topic: '{topic}'.\n"
        f"Key points from their response: {transcript_summary}\n\n"
        f"Generate 3 natural Part {part_number} follow-up questions at an appropriate difficulty level.\n"
        'Return JSON: {"questions": ["<q1>", "<q2>", "<q3>"]}'
    )

    response = model.generate_content(prompt)
    data = _extract_json(response.text)
    return data.get("questions", [])


def score_speaking(part_responses: list[dict]) -> dict:
    """
    Transcribe and score a Speaking section using Gemini audio understanding.

    part_responses: list of dicts with keys:
        part       — int (1, 2, 3)
        question   — str
        audio_bytes — bytes (WebM/Opus from MediaRecorder)
        mime_type  — str (default "audio/webm")

    Returns:
        transcripts, fluency, pronunciation, grammar, vocabulary, overallBand, feedback, ai_model
    """
    import io
    _client()

    model = genai.GenerativeModel(
        model_name=_MODEL_SPEAKING_SCORER,
        system_instruction=(
            f"You are an expert IELTS examiner. Use the following official band descriptors:\n"
            f"{_SPEAKING_BAND_DESCRIPTORS}\n\n"
            "Return ONLY valid JSON with no markdown fencing."
        ),
    )

    # Upload each audio part to the Gemini Files API (48h retention, fine for scoring)
    content_parts = []
    uploaded_files = []
    for r in part_responses:
        audio_bytes = r.get("audio_bytes")
        if not audio_bytes:
            continue
        mime = r.get("mime_type", "audio/webm")
        audio_file = genai.upload_file(
            io.BytesIO(audio_bytes),
            mime_type=mime,
            display_name=f"speaking_part_{r['part']}",
        )
        uploaded_files.append(audio_file)
        content_parts.append(f"Part {r['part']} — Question: {r['question']}")
        content_parts.append(audio_file)

    content_parts.append(
        "Listen to all parts above. First transcribe each part verbatim, then score the full "
        "Speaking section. Return JSON matching this schema exactly:\n"
        "{\n"
        '  "transcripts": [{"part": <int>, "text": "<verbatim transcript>"}],\n'
        '  "fluency": <float 0-9>,\n'
        '  "pronunciation": <float 0-9>,\n'
        '  "grammar": <float 0-9>,\n'
        '  "vocabulary": <float 0-9>,\n'
        '  "overallBand": <float 0-9, average of the four criteria rounded to nearest 0.5>,\n'
        '  "feedback": "<2-3 paragraph narrative feedback>",\n'
        '  "pronunciationFlaggedForReview": <bool>\n'
        "}"
    )

    response = model.generate_content(content_parts)
    result = _extract_json(response.text)
    result["ai_model"] = _MODEL_SPEAKING_SCORER

    # Clean up uploaded files from Gemini's temporary storage
    for f in uploaded_files:
        try:
            genai.delete_file(f.name)
        except Exception:
            pass

    return result


def _build_report_payload(student, sessions_with_sections: list[dict]) -> str:
    """
    Build a structured plain-text payload from the student's selected sessions
    and section types. sessions_with_sections is a list of:
        {"session": <ExamSession>, "section_types": set[str]}
    """
    lines: list[str] = []
    lines.append(f"STUDENT: {student.name} ({student.email})")
    target = student.target_score
    lines.append(f"TARGET BAND: {target if target is not None else 'not set'}")
    lines.append("")

    for entry in sessions_with_sections:
        session = entry["session"]
        wanted = entry["section_types"]
        exam_section_types = [s.type for s in session.exam.sections]
        included_sections = [t for t in exam_section_types if t in wanted]

        lines.append(f"==== EXAM: {session.exam.title} "
                     f"({session.exam.type}) ====")
        lines.append(f"Submitted: {session.submitted_at}")
        lines.append(
            f"Sections in this exam: {len(exam_section_types)} "
            f"({', '.join(exam_section_types) or 'none'})"
        )
        lines.append(
            f"Sections included in this report: {len(included_sections)} "
            f"({', '.join(included_sections) or 'none'})"
        )

        scores_by_type = {s.section_type: s for s in session.scores}
        writing_by_task = {r.task_number: r for r in session.writing_responses}
        speaking_by_part = {r.part_number: r for r in
                            sorted(session.speaking_responses,
                                   key=lambda x: x.part_number)}
        answers_by_question = {a.question_id: a for a in session.answers}

        # Compute and surface the per-exam average band over ONLY the included
        # sections, so the AI doesn't infer a /4 denominator when fewer
        # sections were tested.
        included_band_scores: list[float] = []
        for section in session.exam.sections:
            if section.type not in wanted:
                continue
            score = scores_by_type.get(section.type)
            if score and score.effective_score is not None:
                included_band_scores.append(float(score.effective_score))
        if included_band_scores:
            exam_avg = round(
                sum(included_band_scores) / len(included_band_scores), 2
            )
            lines.append(
                f"Average band across included sections: {exam_avg} "
                f"(computed over {len(included_band_scores)} section"
                f"{'s' if len(included_band_scores) != 1 else ''})"
            )

        for section in session.exam.sections:
            if section.type not in wanted:
                continue
            score = scores_by_type.get(section.type)
            lines.append(f"\n-- Section: {section.type} --")
            if score:
                effective = score.effective_score
                lines.append(f"Band/Score: {effective if effective is not None else 'n/a'}")
                if score.ai_scores:
                    lines.append(f"Criteria: {score.ai_scores}")
                if score.ai_feedback:
                    lines.append(f"AI feedback: {score.ai_feedback}")
                if score.teacher_feedback:
                    lines.append(f"Teacher feedback: {score.teacher_feedback}")
            else:
                lines.append("Band/Score: not yet scored")

            if section.type in ("LISTENING", "READING"):
                lines.append(
                    f"\nRaw item-level answers "
                    f"({len(section.questions)} questions):"
                )
                for q in section.questions:
                    ans = answers_by_question.get(q.id)
                    student_ans = (ans.response_text if ans else None) or "[blank]"
                    correct = q.correct_answer
                    if isinstance(correct, list):
                        correct_str = " / ".join(str(c) for c in correct)
                    else:
                        correct_str = str(correct) if correct is not None else "—"
                    auto = ans.auto_score if ans else None
                    mark = "✓" if auto and float(auto) > 0 else "✗"
                    qtype = q.type
                    lines.append(
                        f"  Q{q.order_index} [{qtype}] {mark}  "
                        f"student=\"{student_ans}\"  correct=\"{correct_str}\""
                    )
            elif section.type == "WRITING":
                for task_num in (1, 2):
                    resp = writing_by_task.get(task_num)
                    if resp and resp.body_text:
                        lines.append(f"\nWriting Task {task_num} "
                                     f"({resp.word_count} words):")
                        lines.append(resp.body_text)
            elif section.type == "SPEAKING":
                for part_num in sorted(speaking_by_part.keys()):
                    resp = speaking_by_part[part_num]
                    transcript = resp.transcript or "[no transcript]"
                    lines.append(f"\nSpeaking Part {part_num} — Q: "
                                 f"{resp.question_text}")
                    lines.append(f"Transcript: {transcript}")

        lines.append("")

    return "\n".join(lines)


def _compute_overall_band(sessions_with_sections: list[dict]) -> float | None:
    """
    Compute an overall IELTS band across all sections included in the report:
    flat average of effective section bands, rounded to nearest 0.5. Returns
    None if no scored sections are included.
    """
    bands: list[float] = []
    for entry in sessions_with_sections:
        session = entry["session"]
        wanted = entry["section_types"]
        for score in session.scores:
            if score.section_type not in wanted:
                continue
            if score.effective_score is None:
                continue
            bands.append(float(score.effective_score))
    if not bands:
        return None
    avg = sum(bands) / len(bands)
    return round(avg * 2) / 2


def generate_student_report(student, sessions_with_sections: list[dict]) -> dict:
    """
    Generate a comprehensive AI report tailored to one student, based on
    selected exam sessions and section types. Uses the modern google-genai
    SDK with the latest Pro model.

    sessions_with_sections: list of dicts with keys:
        session        — ExamSession instance (loaded with relationships)
        section_types  — set/list of SectionType strings to include

    Returns dict: {"report_markdown": str, "ai_model": str, "overall_band": float|None}
    """
    from google import genai as genai_new
    from google.genai import types as genai_types

    client = genai_new.Client(api_key=current_app.config["GEMINI_API_KEY"])

    payload = _build_report_payload(student, sessions_with_sections)
    overall = _compute_overall_band(sessions_with_sections)
    target = student.target_score
    target_line = (f"The student's target band is {target}." if target is not None
                   else "The student has not set a target band.")
    overall_line = (
        f"OVERALL BAND (already shown to the reader at the top of the report): "
        f"{overall}. Do NOT restate this figure as a headline; reference it "
        f"only when discussing the gap to target."
        if overall is not None else
        "No section bands are available; the overall figure cannot be computed."
    )

    system_instruction = (
        "You are a senior IELTS examiner and academic coach producing a "
        "comprehensive, personalised performance report for one student. "
        "Use the official IELTS band descriptors as your frame of "
        "reference.\n\n"
        f"{_WRITING_BAND_DESCRIPTORS}\n{_SPEAKING_BAND_DESCRIPTORS}\n\n"
        "Tone: warm, candid, specific. Cite concrete evidence from the "
        "student's own responses (quote short phrases) — never generic "
        "advice. Return well-formatted Markdown only (no code fences). "
        "Do not mention which AI model or service produced the report."
    )

    prompt = (
        "Below is a structured dump of one student's IELTS practice across "
        "the selected exams and sections. Produce a tailored report with "
        "the following sections, in this order:\n\n"
        "IMPORTANT SCORING RULE — Some exams in this dataset contain fewer "
        "than the standard four sections (Listening / Reading / Writing / "
        "Speaking). When you compute any per-exam average band or overall "
        "average band, you MUST divide by the number of sections actually "
        "tested and included for that exam — never by 4. The payload below "
        "gives you the section count and a pre-computed average per exam; "
        "use those numbers. When you cite an overall figure across multiple "
        "exams, state the denominator explicitly so the reader can see how "
        "it was computed.\n\n"
        f"{overall_line}\n\n"
        "## Executive Summary\n"
        "A 3-4 sentence narrative summary of where this student stands and "
        "the gap to target. Do not lead with the overall band number "
        "(already shown above); instead describe the shape of their "
        "performance — which skills are strongest, which are pulling the "
        "average down.\n\n"
        "## Per-Section Analysis\n"
        "Only cover the sections actually present in the data — do not "
        "fabricate analysis for sections that were not tested. Cite "
        "concrete evidence from the student's own work, explain what is "
        "holding the band down, and call out genuine strengths. For "
        "Listening and Reading, use the item-level answer dump to "
        "diagnose patterns by question type (e.g., 'missed 4/5 "
        "matching-headings' or 'consistent T/F/NG confusion'), and quote "
        "the student's wrong answers when illustrative.\n\n"
        "## Patterns Across Exams\n"
        "Trends visible across multiple sittings: improving, plateauing, or "
        "regressing skills. Reference exam titles. If exams cover different "
        "sets of sections, note that explicitly rather than comparing them "
        "as if equivalent.\n\n"
        "## Priority Action Plan\n"
        "A ranked list of 4-6 concrete next steps, each with a measurable "
        "practice activity. Prioritise the highest-leverage gaps relative "
        "to the target band. If certain sections were never tested, "
        "recommend assessing them before drawing firm conclusions.\n\n"
        "## Predicted Trajectory\n"
        "Realistic timeline to target band, with caveats — including any "
        "caveat about untested sections limiting confidence.\n\n"
        f"{target_line}\n\n"
        "Student data follows:\n\n"
        f"{payload}"
    )

    response = client.models.generate_content(
        model=_MODEL_REPORT,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
        ),
    )
    text = response.text or ""
    # Strip accidental code fences
    text = re.sub(r"^```(?:markdown)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())

    return {
        "report_markdown": text,
        "ai_model": _MODEL_REPORT,
        "overall_band": overall,
    }
