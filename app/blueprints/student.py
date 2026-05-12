from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models.session import ExamSession, SessionStatus

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard")
@login_required
def dashboard():
    assigned = (
        ExamSession.query
        .filter_by(user_id=current_user.id)
        .filter(ExamSession.status.in_([SessionStatus.ASSIGNED, SessionStatus.IN_PROGRESS]))
        .order_by(ExamSession.started_at.desc())
        .all()
    )
    completed = (
        ExamSession.query
        .filter_by(user_id=current_user.id)
        .filter(ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.SCORED]))
        .order_by(ExamSession.submitted_at.desc())
        .all()
    )

    cross_type_stats = _build_cross_session_type_stats(completed)
    readiness = _compute_readiness(current_user, completed)

    return render_template(
        "student/dashboard.html",
        assigned=assigned,
        completed=completed,
        cross_type_stats=cross_type_stats,
        readiness=readiness,
    )


def _build_cross_session_type_stats(sessions: list) -> dict:
    """Aggregate answer accuracy by question type across a list of completed sessions."""
    stats = {}
    for s in sessions:
        answer_map = {a.question_id: a for a in s.answers}
        for section in s.exam.sections:
            if section.type not in ("LISTENING", "READING"):
                continue
            for q in section.questions:
                ans = answer_map.get(q.id)
                is_correct = (
                    ans is not None
                    and ans.auto_score is not None
                    and float(ans.auto_score) > 0
                )
                if q.type not in stats:
                    stats[q.type] = {"correct": 0, "total": 0}
                stats[q.type]["total"] += 1
                if is_correct:
                    stats[q.type]["correct"] += 1
    return stats


def _compute_readiness(user, completed_sessions: list) -> dict | None:
    """
    Returns readiness status based on the last 5 scored sessions vs. target band.
    Returns None if fewer than 2 scored sessions exist.
    """
    scored = [s for s in completed_sessions if s.status == "SCORED" and s.scores]
    recent = scored[:5]
    if len(recent) < 2:
        return None

    band_totals = []
    for s in recent:
        bands = [float(sc.effective_score) for sc in s.scores if sc.effective_score is not None]
        if bands:
            band_totals.append(sum(bands) / len(bands))

    if not band_totals:
        return None

    avg = round(sum(band_totals) / len(band_totals), 1)
    target = float(user.target_score) if user.target_score else 6.5

    if avg >= target:
        status = "GO"
        color = "green"
        message = f"Averaging {avg} — at or above your target of {target}. You are ready."
    elif avg >= target - 0.5:
        status = "BORDERLINE"
        color = "yellow"
        message = f"Averaging {avg} — just below your target of {target}. One more strong mock could confirm readiness."
    else:
        status = "NOT READY"
        color = "red"
        message = f"Averaging {avg} — {round(target - avg, 1)} bands below your target of {target}. Keep practising."

    return {"status": status, "color": color, "message": message, "avg": avg, "sessions": len(recent)}


@student_bp.route("/results/<session_id>")
@login_required
def results(session_id: str):
    session = ExamSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    scores = {s.section_type: s for s in session.scores}

    # Per-question review and per-type accuracy for this session
    answer_map = {a.question_id: a for a in session.answers}
    section_reviews = {}
    type_stats = {}

    for section in session.exam.sections:
        if section.type not in ("LISTENING", "READING"):
            continue
        review = []
        for q in section.questions:
            ans = answer_map.get(q.id)
            is_correct = (
                ans is not None
                and ans.auto_score is not None
                and float(ans.auto_score) > 0
            )
            review.append({"question": q, "answer": ans, "is_correct": is_correct})
            if q.type not in type_stats:
                type_stats[q.type] = {"correct": 0, "total": 0}
            type_stats[q.type]["total"] += 1
            if is_correct:
                type_stats[q.type]["correct"] += 1
        section_reviews[section.type] = review

    return render_template(
        "student/results.html",
        session=session,
        scores=scores,
        section_reviews=section_reviews,
        type_stats=type_stats,
    )
