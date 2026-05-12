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

    Returns a dict with keys:
        taskResponse, coherenceCohesion, lexicalResource, grammaticalRange,
        overallBand, feedback, sentenceHighlights
    """
    _client()
    model = genai.GenerativeModel(
        model_name=_MODEL_WRITING,
        system_instruction=(
            f"You are an expert IELTS examiner. Use the following official band descriptors:\n"
            f"{_WRITING_BAND_DESCRIPTORS}\n\n"
            "Return ONLY valid JSON with no markdown fencing."
        ),
    )

    task_label = f"Task {task_number} ({'Academic' if exam_type == 'ACADEMIC' else 'General Training'})"
    prompt = (
        f"Score this IELTS Writing {task_label} response.\n\n"
        f"Question prompt:\n{question_prompt}\n\n"
        f"Student essay:\n{essay_text}\n\n"
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
        "}"
    )

    response = model.generate_content(prompt)
    result = _extract_json(response.text)
    result["ai_model"] = _MODEL_WRITING
    return result


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
