"""
Exam session lifecycle and scoring orchestration.
"""
import logging
from datetime import datetime, timezone
from ..extensions import db
from ..models.session import ExamSession, Answer, SessionStatus
from ..models.exam import SectionType
from ..models.score import Score
from ..services.band_conversion import listening_band, reading_band

logger = logging.getLogger(__name__)


def _log_ai_error(section: str, session_id: str, exc: Exception) -> None:
    """Log AI scoring errors with a clear message for quota vs other failures."""
    msg = str(exc)
    if "ResourceExhausted" in type(exc).__name__ or "429" in msg or "quota" in msg.lower():
        logger.warning(
            "%s AI scoring skipped for session %s — Gemini quota exceeded. "
            "Enable billing at console.cloud.google.com or wait for quota reset.",
            section, session_id,
        )
    else:
        logger.error("%s AI scoring failed for session %s: %s", section, session_id, exc)


def auto_score_objective_section(session_id: str, section_type: str) -> Score:
    """
    Score Listening or Reading answers against correct_answer keys.
    Creates or updates a Score row for the section.
    """
    session = db.session.get(ExamSession, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found.")

    section = next(
        (s for s in session.exam.sections if s.type == section_type),
        None,
    )
    if not section:
        raise ValueError(f"No {section_type} section in exam {session.exam_id}.")

    question_map = {q.id: q for q in section.questions}
    answers = Answer.query.filter(
        Answer.session_id == session_id,
        Answer.question_id.in_(question_map.keys()),
    ).all()

    raw_correct = 0
    for answer in answers:
        question = question_map[answer.question_id]
        correct = question.correct_answer
        if correct is None:
            continue

        # Normalize comparison: strip whitespace, case-insensitive for text answers
        student_ans = (answer.response_text or "").strip().lower()
        if isinstance(correct, list):
            expected = [str(c).strip().lower() for c in correct]
            is_correct = student_ans in expected
        else:
            is_correct = student_ans == str(correct).strip().lower()

        score_val = float(question.marks) if is_correct else 0.0
        answer.auto_score = score_val
        if is_correct:
            raw_correct += question.marks

    exam_type = session.exam.type
    if section_type == SectionType.LISTENING:
        band = listening_band(raw_correct)
    else:
        band = reading_band(raw_correct, exam_type)

    score_row = Score.query.filter_by(session_id=session_id, section_type=section_type).first()
    if not score_row:
        score_row = Score(session_id=session_id, section_type=section_type)
        db.session.add(score_row)

    score_row.raw_score = raw_correct
    score_row.scaled_score = band
    score_row.scored_at = datetime.now(timezone.utc)
    score_row.is_finalized = True
    db.session.commit()
    return score_row


def compute_overall_band(session_id: str) -> float | None:
    """Average all finalized section bands into an overall IELTS band score."""
    from .band_conversion import overall_band
    session = db.session.get(ExamSession, session_id)
    if not session:
        return None
    bands = [float(s.scaled_score) for s in session.scores if s.scaled_score is not None]
    return overall_band(bands) if bands else None


def enqueue_scoring(session_id: str) -> None:
    """
    Enqueue async AI scoring for Writing and Speaking via rq.
    Falls back to a background thread if Redis is unavailable — never blocks the HTTP response.
    """
    try:
        import redis
        from rq import Queue
        from flask import current_app

        r = redis.from_url(current_app.config["REDIS_URL"])
        # Ping first so ConnectionError is raised here (inside the try) rather
        # than inside Queue.enqueue where it would escape the except clause.
        r.ping()
        Queue(connection=r).enqueue(_run_ai_scoring, session_id)
    except Exception:
        import threading
        from flask import current_app
        app = current_app._get_current_object()

        def _run():
            with app.app_context():
                _run_ai_scoring(session_id)

        threading.Thread(target=_run, daemon=True).start()


def _run_ai_scoring(session_id: str) -> None:
    """
    Full scoring pipeline for a submitted session.
    Called by rq worker or synchronously as fallback.
    """
    from .ai_scoring import score_writing
    from .band_conversion import writing_band_from_criteria

    session = db.session.get(ExamSession, session_id)
    if not session or session.status != SessionStatus.SUBMITTED:
        return

    # Score objective sections
    for section in session.exam.sections:
        if section.type in (SectionType.LISTENING, SectionType.READING):
            auto_score_objective_section(session_id, section.type)

    # Score Writing (Phase 2)
    for writing_resp in session.writing_responses:
        section = next(s for s in session.exam.sections if s.type == SectionType.WRITING)
        task_prompt = section.config.get(f"task{writing_resp.task_number}Prompt", "")
        try:
            result = score_writing(
                task_number=writing_resp.task_number,
                question_prompt=task_prompt,
                essay_text=writing_resp.body_text,
                exam_type=session.exam.type,
            )
            band = writing_band_from_criteria(
                result["taskResponse"],
                result["coherenceCohesion"],
                result["lexicalResource"],
                result["grammaticalRange"],
            )
            score_row = Score.query.filter_by(
                session_id=session_id, section_type=SectionType.WRITING
            ).first()
            if not score_row:
                score_row = Score(session_id=session_id, section_type=SectionType.WRITING)
                db.session.add(score_row)
            score_row.scaled_score = band
            score_row.ai_scores = result
            score_row.ai_feedback = result.get("feedback")
            score_row.sentence_highlights = result.get("sentenceHighlights")
            score_row.ai_model = result.get("ai_model")
            score_row.scored_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            _log_ai_error("Writing", session_id, e)

    # Score Speaking (Phase 3)
    speaking_responses = sorted(session.speaking_responses, key=lambda r: r.part_number)
    if speaking_responses:
        from .ai_scoring import score_speaking
        from .storage import download_bytes
        try:
            part_responses = []
            for r in speaking_responses:
                audio_bytes = None
                if r.audio_file_key:
                    audio_bytes = download_bytes(r.audio_file_key)
                part_responses.append({
                    "part": r.part_number,
                    "question": r.question_text,
                    "audio_bytes": audio_bytes,
                    "mime_type": "audio/webm",
                })

            if not any(p.get("audio_bytes") for p in part_responses):
                logger.warning("Speaking scoring skipped for session %s — no audio files found.", session_id)
                raise ValueError("No audio recordings to score.")

            result = score_speaking(part_responses)

            # Persist transcripts back to each SpeakingResponse row
            for t in result.get("transcripts", []):
                row = next((r for r in speaking_responses if r.part_number == t["part"]), None)
                if row:
                    row.transcript = t.get("text", "")

            score_row = Score.query.filter_by(session_id=session_id, section_type=SectionType.SPEAKING).first()
            if not score_row:
                score_row = Score(session_id=session_id, section_type=SectionType.SPEAKING)
                db.session.add(score_row)
            score_row.scaled_score = result.get("overallBand", 0)
            score_row.ai_scores = result
            score_row.ai_feedback = result.get("feedback")
            score_row.ai_model = result.get("ai_model")
            score_row.scored_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            _log_ai_error("Speaking", session_id, e)

    session.status = SessionStatus.SCORED
    db.session.commit()
