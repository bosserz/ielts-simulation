import uuid
from datetime import datetime, timezone
from ..extensions import db


class WritingResponse(db.Model):
    __tablename__ = "ielts_writing_responses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("ielts_exam_sessions.id"), nullable=False)
    task_number = db.Column(db.Integer, nullable=False)   # 1 or 2
    body_text = db.Column(db.Text, nullable=False, default="")
    word_count = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("session_id", "task_number", name="uq_ielts_writing_session_task"),
    )

    session = db.relationship("ExamSession", back_populates="writing_responses")

    def __repr__(self) -> str:
        return f"<WritingResponse task={self.task_number} words={self.word_count}>"


class SpeakingResponse(db.Model):
    __tablename__ = "ielts_speaking_responses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("ielts_exam_sessions.id"), nullable=False)
    part_number = db.Column(db.Integer, nullable=False)   # 1, 2, or 3
    question_text = db.Column(db.Text, nullable=False)
    audio_file_key = db.Column(db.String(512), nullable=True)   # R2 storage key
    transcript = db.Column(db.Text, nullable=True)              # Web Speech API output
    duration_s = db.Column(db.Integer, nullable=True)
    recorded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = db.relationship("ExamSession", back_populates="speaking_responses")

    def __repr__(self) -> str:
        return f"<SpeakingResponse part={self.part_number} duration={self.duration_s}s>"
