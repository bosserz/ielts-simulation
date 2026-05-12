import uuid
from datetime import datetime
from ..extensions import db


class Score(db.Model):
    __tablename__ = "ielts_scores"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("ielts_exam_sessions.id"), nullable=False)
    section_type = db.Column(db.String(20), nullable=False)
    # scaled_score holds platform-native scores: IELTS bands (0–9) or SAT section scores (200–800)
    scaled_score = db.Column(db.Numeric(5, 1), nullable=True)
    raw_score = db.Column(db.Integer, nullable=True)          # number correct; meaning varies per platform

    # Criterion breakdown from Gemini
    # Writing: {taskResponse, coherenceCohesion, lexicalResource, grammaticalRange}
    # Speaking: {fluency, pronunciation, grammar, vocabulary}
    ai_scores = db.Column(db.JSON, nullable=True)
    ai_feedback = db.Column(db.Text, nullable=True)
    ai_model = db.Column(db.String(100), nullable=True)       # model version for audit

    # Sentence complexity annotations from Phase 2
    sentence_highlights = db.Column(db.JSON, nullable=True)

    # Teacher overrides
    teacher_override_score = db.Column(db.Numeric(5, 1), nullable=True)
    teacher_feedback = db.Column(db.Text, nullable=True)
    teacher_feedback_audio_key = db.Column(db.String(512), nullable=True)

    is_finalized = db.Column(db.Boolean, nullable=False, default=False)
    scored_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("session_id", "section_type", name="uq_ielts_score_session_section"),
    )

    session = db.relationship("ExamSession", back_populates="scores")

    @property
    def effective_score(self) -> float | None:
        """Returns teacher override if set, otherwise the AI/auto-computed score."""
        if self.teacher_override_score is not None:
            return float(self.teacher_override_score)
        return float(self.scaled_score) if self.scaled_score is not None else None

    def __repr__(self) -> str:
        return f"<Score {self.section_type} score={self.effective_score}>"
