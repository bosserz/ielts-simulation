import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, abort, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models.session import ExamSession, SessionStatus
from ..models.exam import SectionType
from ..models.response import WritingResponse

logger = logging.getLogger(__name__)

exam_bp = Blueprint("exam", __name__, url_prefix="/exam")


def _get_active_session(session_id: str) -> ExamSession:
    """Returns an in-progress session that belongs to the current user, or 404."""
    session = ExamSession.query.filter_by(
        id=session_id,
        user_id=current_user.id,
        status=SessionStatus.IN_PROGRESS,
    ).first_or_404()
    return session


def _get_session_for_view(session_id: str):
    """
    Returns the session if IN_PROGRESS.
    Redirects to results if already SUBMITTED or SCORED (handles stuck sessions).
    Raises 404 if session not found or belongs to another user.
    """
    from flask import redirect as _redirect, url_for as _url_for
    session = ExamSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first_or_404()
    if session.status in (SessionStatus.SUBMITTED, SessionStatus.SCORED):
        return None, _redirect(_url_for("student.results", session_id=session_id))
    if session.status != SessionStatus.IN_PROGRESS:
        abort(409, "Session is not in progress.")
    return session, None


def _next_section(exam_session: ExamSession):
    """Returns the Section that follows the current one, or None if this is the last."""
    sections = exam_session.exam.sections  # already ordered by order_index
    for i, s in enumerate(sections):
        if s.id == exam_session.current_section_id:
            return sections[i + 1] if i + 1 < len(sections) else None
    return None


def _save_writing_from_form(exam_session: ExamSession) -> None:
    """If the current section is WRITING and the form has task texts, persist
    them to the DB and mirror to R2."""
    import io, json as _json
    section = exam_session.current_section
    if not section or section.type != SectionType.WRITING:
        return

    for task_num in (1, 2):
        text = (request.form.get(f"task{task_num}_text", "") or "").strip()
        if not text:
            continue
        word_count = len(text.split())

        draft = WritingResponse.query.filter_by(
            session_id=exam_session.id, task_number=task_num
        ).first()
        if draft:
            draft.body_text = text
            draft.word_count = word_count
        else:
            draft = WritingResponse(
                session_id=exam_session.id, task_number=task_num,
                body_text=text, word_count=word_count,
            )
            db.session.add(draft)

        # Mirror to R2
        try:
            from ..services.storage import upload_fileobj
            task_prompt = section.config.get(f"task{task_num}Prompt", "")
            payload = _json.dumps({
                "session_id": exam_session.id,
                "task_number": task_num,
                "exam_type": exam_session.exam.type,
                "question_prompt": task_prompt,
                "essay_text": text,
                "word_count": word_count,
            }, ensure_ascii=False, indent=2)
            upload_fileobj(
                io.BytesIO(payload.encode("utf-8")),
                f"writing/{exam_session.id}/task{task_num}.json",
                content_type="application/json",
            )
            logger.info("Writing task %s saved to R2 for session %s", task_num, exam_session.id)
        except Exception as e:
            logger.exception("R2 upload failed for session %s task %s: %s",
                             exam_session.id, task_num, e)

    db.session.commit()


@exam_bp.route("/<session_id>/advance", methods=["POST"])
@login_required
def advance(session_id: str):
    """Advance to the next section, or submit if this was the last one."""
    exam_session = ExamSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first_or_404()
    if exam_session.status in (SessionStatus.SUBMITTED, SessionStatus.SCORED):
        return redirect(url_for("exam.submit", session_id=session_id), code=307)
    if exam_session.status != SessionStatus.IN_PROGRESS:
        abort(409)
    _save_writing_from_form(exam_session)
    nxt = _next_section(exam_session)
    if nxt is None:
        return redirect(url_for("exam.submit", session_id=session_id), code=307)
    exam_session.current_section_id = nxt.id
    exam_session.time_remaining_s = nxt.time_limit_s
    db.session.commit()
    return redirect(url_for(f"exam.{nxt.type.lower()}", session_id=session_id))


@exam_bp.route("/<session_id>/start", methods=["POST"])
@login_required
def start(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    if session.status != SessionStatus.ASSIGNED:
        abort(409, "Session already started or completed.")

    first_section = session.exam.sections[0] if session.exam.sections else None
    if not first_section:
        abort(422, "Exam has no sections.")

    session.start(
        section_id=first_section.id,
        request_meta={"ip": request.remote_addr, "user_agent": request.user_agent.string},
    )
    db.session.commit()
    return redirect(url_for(f"exam.{first_section.type.lower()}", session_id=session_id))


@exam_bp.route("/<session_id>/listening")
@login_required
def listening(session_id: str):
    exam_session, redir = _get_session_for_view(session_id)
    if redir:
        return redir
    section = exam_session.current_section
    if section.type != SectionType.LISTENING:
        abort(409)

    config = section.config or {}
    parts = config.get("parts", [])
    part_index = request.args.get("partIndex", 0, type=int)
    part_index = max(0, min(part_index, max(len(parts) - 1, 0)))

    played = list(exam_session.listening_parts_played or [])
    part_already_played = part_index in played

    # Filter questions to the current part via group_id; fall back to all questions
    if parts:
        current_part = parts[part_index]
        group_id = current_part.get("questionGroupId") or current_part.get("groupId")
        if group_id:
            part_questions = [q for q in section.questions if str(q.group_id) == str(group_id)]
        else:
            # Part has no group binding — divide questions evenly across parts
            all_qs = sorted(section.questions, key=lambda q: q.order_index)
            chunk = max(1, len(all_qs) // len(parts))
            start = part_index * chunk
            end = start + chunk if part_index < len(parts) - 1 else len(all_qs)
            part_questions = all_qs[start:end]
    else:
        current_part = {}
        part_questions = sorted(section.questions, key=lambda q: q.order_index)

    is_last_part = part_index >= len(parts) - 1

    return render_template(
        "exam/listening.html",
        session=exam_session,
        section=section,
        questions=part_questions,
        parts=parts,
        part_index=part_index,
        current_part=current_part,
        part_already_played=part_already_played,
        is_last_part=is_last_part,
        next_section=_next_section(exam_session),
    )


@exam_bp.route("/<session_id>/reading")
@login_required
def reading(session_id: str):
    exam_session, redir = _get_session_for_view(session_id)
    if redir:
        return redir
    section = exam_session.current_section
    if section.type != SectionType.READING:
        abort(409)
    existing_annotations = {
        a.id: a for a in exam_session.annotations
        if a.passage_group_id in {q.group_id for q in section.questions}
    }
    return render_template(
        "exam/reading.html",
        session=exam_session,
        section=section,
        questions=section.questions,
        annotations=list(existing_annotations.values()),
        next_section=_next_section(exam_session),
    )


@exam_bp.route("/<session_id>/writing")
@login_required
def writing(session_id: str):
    exam_session, redir = _get_session_for_view(session_id)
    if redir:
        return redir
    section = exam_session.current_section
    if section.type != SectionType.WRITING:
        abort(409)
    drafts = {r.task_number: r for r in exam_session.writing_responses}
    return render_template(
        "exam/writing.html",
        session=exam_session,
        section=section,
        drafts=drafts,
        next_section=_next_section(exam_session),
    )


@exam_bp.route("/<session_id>/speaking")
@login_required
def speaking(session_id: str):
    exam_session, redir = _get_session_for_view(session_id)
    if redir:
        return redir
    section = exam_session.current_section
    if section.type != SectionType.SPEAKING:
        abort(409)
    return render_template(
        "exam/speaking.html",
        session=exam_session,
        section=section,
        next_section=_next_section(exam_session),
    )


@exam_bp.route("/<session_id>/submit", methods=["POST"])
@login_required
def submit(session_id: str):
    exam_session = ExamSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first_or_404()

    # Already fully scored — just show results.
    if exam_session.status == SessionStatus.SCORED:
        return redirect(url_for("student.results", session_id=session_id))

    # SUBMITTED means a previous attempt committed the status but scoring failed
    # (e.g. a Gemini quota error before billing was enabled). Re-enqueue scoring.
    if exam_session.status not in (SessionStatus.IN_PROGRESS, SessionStatus.SUBMITTED):
        abort(409, "Session cannot be submitted in its current state.")

    if exam_session.status == SessionStatus.IN_PROGRESS:
        _save_writing_from_form(exam_session)
        exam_session.status = SessionStatus.SUBMITTED
        exam_session.submitted_at = datetime.now(timezone.utc)
        db.session.commit()

    try:
        from ..services.exam_engine import enqueue_scoring
        enqueue_scoring(session_id)
    except Exception as e:
        logger.error("Scoring enqueue failed for session %s: %s", session_id, e)

    return redirect(url_for("student.results", session_id=session_id))
