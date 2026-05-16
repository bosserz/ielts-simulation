import uuid
from datetime import datetime, timezone
from ..extensions import db


class StudentReport(db.Model):
    __tablename__ = "ielts_student_reports"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey("ielts_users.id"), nullable=False)
    generated_by = db.Column(db.String(36), db.ForeignKey("ielts_users.id"), nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # JSON: [{"session_id": "...", "exam_title": "...", "section_types": ["LISTENING", "WRITING"]}]
    selections = db.Column(db.JSON, nullable=False, default=list)

    # Snapshot of student.target_score when the report was generated
    target_band_snapshot = db.Column(db.Numeric(5, 1), nullable=True)

    # Computed overall IELTS band at the time of generation. Average across
    # all included sections (with bands), rounded to nearest 0.5. Stored so
    # the figure stays stable even if underlying scores later change.
    overall_band_snapshot = db.Column(db.Numeric(5, 1), nullable=True)

    report_markdown = db.Column(db.Text, nullable=False)
    ai_model = db.Column(db.String(100), nullable=True)

    student = db.relationship("User", foreign_keys=[student_id])
    author = db.relationship("User", foreign_keys=[generated_by])

    def __repr__(self) -> str:
        return f"<StudentReport student={self.student_id[:8]} at={self.generated_at}>"
