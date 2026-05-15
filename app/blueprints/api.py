"""
HTMX endpoint collection and JSON API for JS fetch calls.
All routes return either an HTML fragment (for HTMX swaps) or JSON (for JS fetch).
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, abort, Response, stream_with_context

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from ..extensions import db
from ..models.session import ExamSession, Answer, SessionStatus
from ..models.response import WritingResponse, SpeakingResponse
from ..models.annotation import Annotation

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Health / connectivity check
# ---------------------------------------------------------------------------

@api_bp.route("/ping")
def ping():
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Signed audio URL — fetched by audio-player.js on Listening section load
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/audio-url")
@login_required
def audio_url(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    section = session.current_section
    if not section:
        return jsonify({"url": None, "parts": []})

    config = section.config or {}
    parts = config.get("parts", [])

    # Multi-part: ?partIndex=0 fetches a specific part's audio
    part_index = request.args.get("partIndex", type=int)
    if part_index is not None and parts:
        if 0 <= part_index < len(parts):
            audio_key = parts[part_index].get("audioFileKey")
        else:
            return jsonify({"url": None, "parts": parts})
    elif parts:
        # Default to first part when no index given
        audio_key = parts[0].get("audioFileKey")
    else:
        # Legacy single-audio config
        audio_key = config.get("audioFileKey")

    if not audio_key:
        return jsonify({"url": None, "parts": parts})

    try:
        from ..services.storage import get_signed_download_url
        url = get_signed_download_url(audio_key, expires_in=7200)
        return jsonify({"url": url, "parts": parts})
    except Exception:
        # R2 not configured in dev — return null so the player shows a graceful message
        return jsonify({"url": None, "parts": parts})


# ---------------------------------------------------------------------------
# Audio proxy — streams R2 audio through Flask to avoid CORS issues
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/audio-proxy")
@login_required
def audio_proxy(session_id: str):
    import urllib.request
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    section = session.current_section
    if not section:
        abort(404)

    config = section.config or {}
    parts = config.get("parts", [])

    part_index = request.args.get("partIndex", type=int)
    if part_index is not None and parts:
        if 0 <= part_index < len(parts):
            audio_key = parts[part_index].get("audioFileKey")
        else:
            abort(404)
    elif parts:
        audio_key = parts[0].get("audioFileKey")
    else:
        audio_key = config.get("audioFileKey")

    if not audio_key:
        abort(404)

    try:
        from ..services.storage import get_signed_download_url
        signed_url = get_signed_download_url(audio_key, expires_in=300)
    except Exception:
        abort(503)

    try:
        r = urllib.request.urlopen(signed_url)
    except Exception:
        abort(502)

    content_type = r.headers.get("Content-Type", "audio/wav")

    def generate():
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            yield chunk

    return Response(
        stream_with_context(generate()),
        status=200,
        content_type=content_type,
        headers={"Accept-Ranges": "none"},
    )


# ---------------------------------------------------------------------------
# Session heartbeat — keeps time_remaining_s server-authoritative
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/heartbeat", methods=["POST"])
@login_required
def heartbeat(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "time_remaining_s" in data:
        session.time_remaining_s = int(data["time_remaining_s"])
        db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Audio played — mark one-time play on the server
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/audio-played", methods=["POST"])
@login_required
def audio_played(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    part_index = data.get("partIndex", 0)

    played = list(session.listening_parts_played or [])
    if part_index not in played:
        played.append(part_index)
        session.listening_parts_played = played

    # Keep legacy audio_played_at for the first part
    if session.audio_played_at is None:
        session.audio_played_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"ok": True, "partsPlayed": played})


# ---------------------------------------------------------------------------
# Answers — batch upsert (called by IndexedDB sync queue)
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/answers/batch", methods=["PATCH"])
@login_required
def batch_save_answers(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    if session.status != SessionStatus.IN_PROGRESS:
        abort(409, "Session is not in progress.")

    data = request.get_json(silent=True) or {}
    events = data.get("events", [])

    for event in events:
        question_id = event.get("questionId")
        new_value = event.get("newValue")
        if not question_id:
            continue

        answer = Answer.query.filter_by(session_id=session_id, question_id=question_id).first()
        if answer:
            answer.response_text = new_value
        else:
            answer = Answer(session_id=session_id, question_id=question_id, response_text=new_value)
            db.session.add(answer)

    db.session.commit()
    return jsonify({"ok": True, "synced": len(events)})


# ---------------------------------------------------------------------------
# Flag toggle — upserts Answer.is_flagged by question ID
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/flag", methods=["POST"])
@login_required
def flag_question(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    if session.status != SessionStatus.IN_PROGRESS:
        abort(409, "Session is not in progress.")

    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    if not question_id:
        abort(400, "question_id required")

    flagged = bool(data.get("flagged"))

    answer = Answer.query.filter_by(session_id=session_id, question_id=question_id).first()
    if answer:
        answer.is_flagged = flagged
    else:
        answer = Answer(session_id=session_id, question_id=question_id, is_flagged=flagged)
        db.session.add(answer)

    db.session.commit()
    return jsonify({"ok": True, "flagged": flagged})


# ---------------------------------------------------------------------------
# Writing autosave — called by writing.js every 10 seconds
# ---------------------------------------------------------------------------

@api_bp.route("/writing/<session_id>/autosave", methods=["POST"])
@login_required
def writing_autosave(session_id: str):
    import io, json as _json
    exam_session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    task_number = int(data.get("task", 1))
    body_text = data.get("text", "")
    word_count = len(body_text.split()) if body_text.strip() else 0

    draft = WritingResponse.query.filter_by(session_id=session_id, task_number=task_number).first()
    if draft:
        draft.body_text = body_text
        draft.word_count = word_count
    else:
        draft = WritingResponse(
            session_id=session_id, task_number=task_number,
            body_text=body_text, word_count=word_count,
        )
        db.session.add(draft)

    db.session.commit()

    # Mirror the latest draft to R2 so there is always an up-to-date copy
    # independent of the AI scoring pipeline.
    r2_uploaded = False
    if body_text.strip():
        try:
            from ..services.storage import upload_fileobj
            writing_section = next(
                (s for s in exam_session.exam.sections if s.type == "WRITING"), None
            )
            task_prompt = (
                writing_section.config.get(f"task{task_number}Prompt", "")
                if writing_section else ""
            )
            payload = _json.dumps({
                "session_id": session_id,
                "task_number": task_number,
                "exam_type": exam_session.exam.type,
                "question_prompt": task_prompt,
                "essay_text": body_text,
                "word_count": word_count,
            }, ensure_ascii=False, indent=2)
            r2_key = f"writing/{session_id}/task{task_number}.json"
            upload_fileobj(
                io.BytesIO(payload.encode("utf-8")),
                r2_key,
                content_type="application/json",
            )
            r2_uploaded = True
            logger.info("Writing task %s saved to R2 at %s", task_number, r2_key)
        except Exception as e:
            logger.exception("R2 upload failed for writing session %s task %s: %s",
                             session_id, task_number, e)

    return jsonify({"ok": True, "word_count": word_count, "r2_uploaded": r2_uploaded})


# ---------------------------------------------------------------------------
# Speaking part save — called by speaking.html JS after each part is recorded
# ---------------------------------------------------------------------------

@api_bp.route("/sessions/<session_id>/speaking/parts", methods=["POST"])
@login_required
def save_speaking_part(session_id: str):
    ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    audio_file_key = None
    if request.content_type and "multipart/form-data" in request.content_type:
        part_number = int(request.form.get("part", 1))
        question_text = request.form.get("question", "")
        duration_s = request.form.get("duration_s", type=int)
        audio = request.files.get("audio")
        if audio:
            from ..services.storage import upload_fileobj
            mime = audio.content_type or "audio/webm"
            # Normalise extension: webm for everything MediaRecorder produces
            key = f"speaking/{session_id}/part_{part_number}.webm"
            upload_fileobj(audio.stream, key, mime)
            audio_file_key = key
    else:
        data = request.get_json(silent=True) or {}
        part_number = int(data.get("part", 1))
        question_text = data.get("question", "")
        duration_s = data.get("duration_s")

    resp = SpeakingResponse.query.filter_by(session_id=session_id, part_number=part_number).first()
    if resp:
        resp.question_text = question_text
        if audio_file_key:
            resp.audio_file_key = audio_file_key
        if duration_s is not None:
            resp.duration_s = int(duration_s)
    else:
        resp = SpeakingResponse(
            session_id=session_id,
            part_number=part_number,
            question_text=question_text,
            audio_file_key=audio_file_key,
            duration_s=int(duration_s) if duration_s is not None else None,
        )
        db.session.add(resp)

    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Annotations — save Reading highlight / note
# ---------------------------------------------------------------------------

@api_bp.route("/annotations", methods=["POST"])
@login_required
def save_annotation():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    annotation = Annotation(
        session_id=session_id,
        passage_group_id=data.get("passage_group_id", ""),
        start_offset=int(data.get("start_offset", 0)),
        end_offset=int(data.get("end_offset", 0)),
        selected_text=data.get("selected_text", ""),
        note=data.get("note"),
        color=data.get("color", "yellow"),
    )
    db.session.add(annotation)
    db.session.commit()
    return jsonify({"ok": True, "id": annotation.id})


@api_bp.route("/annotations/<annotation_id>", methods=["DELETE"])
@login_required
def delete_annotation(annotation_id: str):
    annotation = Annotation.query.filter_by(id=annotation_id).first_or_404()
    if annotation.session.user_id != current_user.id:
        abort(403)
    db.session.delete(annotation)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Score status polling — returns an HTML fragment for HTMX outerHTML swap.
# The fragment re-includes the hx-trigger while pending, so polling continues.
# ---------------------------------------------------------------------------

_WRITING_PENDING_FRAGMENT = """\
<div id="writing-score-pending"
     class="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-6 text-center text-sm text-gray-500"
     hx-get="/api/sessions/{session_id}/score-status"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  <p class="mb-1">AI scoring in progress…</p>
  <p class="text-xs text-gray-400">This page will update automatically when scoring is complete.</p>
</div>
"""

_WRITING_SCORED_FRAGMENT = """\
<div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
  <h2 class="font-semibold mb-3">Writing Feedback</h2>
  {criteria_html}
  <p class="text-sm text-gray-700 whitespace-pre-line">{feedback}</p>
</div>
"""

_WRITING_CRITERIA_FRAGMENT = """\
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
    <div class="bg-gray-50 rounded p-3">
      <p class="text-gray-500 text-xs mb-1">Task Response</p>
      <p class="font-bold text-lg">{taskResponse}</p>
    </div>
    <div class="bg-gray-50 rounded p-3">
      <p class="text-gray-500 text-xs mb-1">Coherence &amp; Cohesion</p>
      <p class="font-bold text-lg">{coherenceCohesion}</p>
    </div>
    <div class="bg-gray-50 rounded p-3">
      <p class="text-gray-500 text-xs mb-1">Lexical Resource</p>
      <p class="font-bold text-lg">{lexicalResource}</p>
    </div>
    <div class="bg-gray-50 rounded p-3">
      <p class="text-gray-500 text-xs mb-1">Grammar Range</p>
      <p class="font-bold text-lg">{grammaticalRange}</p>
    </div>
  </div>
"""


@api_bp.route("/sessions/<session_id>/score-status")
@login_required
def score_status(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()

    if session.status != SessionStatus.SCORED:
        return _WRITING_PENDING_FRAGMENT.format(session_id=session_id), 200

    writing_score = next(
        (s for s in session.scores if s.section_type == "WRITING"), None
    )
    if not writing_score or not writing_score.ai_feedback:
        return _WRITING_PENDING_FRAGMENT.format(session_id=session_id), 200

    criteria_html = ""
    if writing_score.ai_scores:
        ai = writing_score.ai_scores
        criteria_html = _WRITING_CRITERIA_FRAGMENT.format(
            taskResponse=ai.get("taskResponse", "—"),
            coherenceCohesion=ai.get("coherenceCohesion", "—"),
            lexicalResource=ai.get("lexicalResource", "—"),
            grammaticalRange=ai.get("grammaticalRange", "—"),
        )

    return _WRITING_SCORED_FRAGMENT.format(
        criteria_html=criteria_html,
        feedback=writing_score.ai_feedback,
    ), 200
