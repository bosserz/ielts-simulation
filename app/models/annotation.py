import uuid
from datetime import datetime, timezone
from ..extensions import db


class Annotation(db.Model):
    __tablename__ = "ielts_annotations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("ielts_exam_sessions.id"), nullable=False)
    passage_group_id = db.Column(db.String(36), nullable=False)  # FK to Question.group_id
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    selected_text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(20), nullable=False, default="yellow")  # yellow, pink, blue
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = db.relationship("ExamSession", back_populates="annotations")

    def __repr__(self) -> str:
        return f"<Annotation [{self.start_offset}:{self.end_offset}] color={self.color}>"
