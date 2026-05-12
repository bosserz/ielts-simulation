import uuid
from datetime import datetime, timezone
from ..extensions import db


class SessionStatus:
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    SCORED = "SCORED"


class ExamSession(db.Model):
    __tablename__ = "ielts_exam_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey("ielts_exams.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("ielts_users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=SessionStatus.ASSIGNED)
    started_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    current_section_id = db.Column(db.String(36), db.ForeignKey("ielts_sections.id"), nullable=True)
    time_remaining_s = db.Column(db.Integer, nullable=True)
    # Server-side guard: once set, Listening audio cannot replay
    audio_played_at = db.Column(db.DateTime, nullable=True)
    # JSON list of part indices whose audio clip has been played, e.g. [0, 1, 2]
    listening_parts_played = db.Column(db.JSON, nullable=True, default=list)
    # JSON array of tab-switch events for integrity monitoring
    focus_lost_events = db.Column(db.JSON, nullable=False, default=list)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    exam = db.relationship("Exam", back_populates="sessions")
    user = db.relationship("User", back_populates="sessions")
    current_section = db.relationship("Section", foreign_keys=[current_section_id])
    answers = db.relationship("Answer", back_populates="session", cascade="all, delete-orphan")
    writing_responses = db.relationship("WritingResponse", back_populates="session", cascade="all, delete-orphan")
    speaking_responses = db.relationship("SpeakingResponse", back_populates="session", cascade="all, delete-orphan")
    scores = db.relationship("Score", back_populates="session", cascade="all, delete-orphan")
    annotations = db.relationship("Annotation", back_populates="session", cascade="all, delete-orphan")

    def start(self, section_id: str, request_meta: dict | None = None) -> None:
        self.status = SessionStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
        self.current_section_id = section_id
        if request_meta:
            self.ip_address = request_meta.get("ip")
            self.user_agent = request_meta.get("user_agent")

    def __repr__(self) -> str:
        return f"<ExamSession {self.id[:8]} user={self.user_id[:8]} [{self.status}]>"


class Answer(db.Model):
    __tablename__ = "ielts_answers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("ielts_exam_sessions.id"), nullable=False)
    question_id = db.Column(db.String(36), db.ForeignKey("ielts_questions.id"), nullable=False)
    response_text = db.Column(db.Text, nullable=True)
    is_flagged = db.Column(db.Boolean, nullable=False, default=False)
    # 1.0 = correct, 0.0 = incorrect, null = not yet scored (Writing/Speaking)
    auto_score = db.Column(db.Numeric(4, 2), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("session_id", "question_id", name="uq_ielts_answer_session_question"),
    )

    session = db.relationship("ExamSession", back_populates="answers")
    question = db.relationship("Question", back_populates="answers")

    def __repr__(self) -> str:
        return f"<Answer q={self.question_id[:8]} score={self.auto_score}>"
