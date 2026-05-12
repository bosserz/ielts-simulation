import uuid
from datetime import datetime, timezone
from ..extensions import db


class Platform:
    IELTS = "IELTS"
    SAT = "SAT"


class ExamType:
    # IELTS variants
    ACADEMIC = "ACADEMIC"
    GENERAL_TRAINING = "GENERAL_TRAINING"
    # SAT variants
    DIGITAL_SAT = "DIGITAL_SAT"


class ExamStatus:
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SectionType:
    # IELTS sections
    LISTENING = "LISTENING"
    READING = "READING"
    WRITING = "WRITING"
    SPEAKING = "SPEAKING"
    # SAT sections (Digital SAT format)
    READING_WRITING = "READING_WRITING"     # SAT Module 1 & 2 (RW)
    MATH = "MATH"                           # SAT Module 1 & 2 (Math)


class QuestionType:
    # Shared across platforms
    MCQ = "MCQ"
    SHORT_ANSWER = "SHORT_ANSWER"
    # IELTS-specific
    TFNG = "TFNG"                           # True/False/Not Given
    YNGNG = "YNGNG"                         # Yes/No/Not Given
    MATCHING_HEADINGS = "MATCHING_HEADINGS"
    MATCHING_FEATURES = "MATCHING_FEATURES"
    SENTENCE_COMPLETION = "SENTENCE_COMPLETION"
    NOTE_COMPLETION = "NOTE_COMPLETION"
    TABLE_COMPLETION = "TABLE_COMPLETION"
    DIAGRAM_LABELLING = "DIAGRAM_LABELLING"
    SUMMARY_COMPLETION = "SUMMARY_COMPLETION"
    # SAT-specific
    GRID_IN = "GRID_IN"                     # SAT Math student-produced response
    EVIDENCE_BASED = "EVIDENCE_BASED"       # SAT paired passage evidence question


class Exam(db.Model):
    __tablename__ = "ielts_exams"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    platform = db.Column(db.String(20), nullable=False, default=Platform.IELTS)
    type = db.Column(db.String(20), nullable=False, default=ExamType.ACADEMIC)
    status = db.Column(db.String(20), nullable=False, default=ExamStatus.DRAFT)
    created_by = db.Column(db.String(36), db.ForeignKey("ielts_users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    creator = db.relationship("User", back_populates="created_exams")
    sections = db.relationship("Section", back_populates="exam", order_by="Section.order_index", cascade="all, delete-orphan")
    sessions = db.relationship("ExamSession", back_populates="exam", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Exam '{self.title}' [{self.status}]>"


class Section(db.Model):
    __tablename__ = "ielts_sections"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey("ielts_exams.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    time_limit_s = db.Column(db.Integer, nullable=False)
    # JSONB in PostgreSQL; falls back to JSON in SQLite for dev
    config = db.Column(db.JSON, nullable=False, default=dict)

    exam = db.relationship("Exam", back_populates="sections")
    questions = db.relationship("Question", back_populates="section", order_by="Question.order_index", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Section {self.type} #{self.order_index}>"


class Question(db.Model):
    __tablename__ = "ielts_questions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    section_id = db.Column(db.String(36), db.ForeignKey("ielts_sections.id"), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(40), nullable=False)
    prompt = db.Column(db.Text, nullable=True)
    options = db.Column(db.JSON, nullable=True)          # MCQ choices: [{id, text}]
    correct_answer = db.Column(db.JSON, nullable=True)   # auto-marked types only
    # Groups questions that share the same passage/audio segment
    group_id = db.Column(db.String(36), nullable=True)
    marks = db.Column(db.Integer, nullable=False, default=1)
    metadata_ = db.Column("metadata", db.JSON, nullable=True)

    section = db.relationship("Section", back_populates="questions")
    answers = db.relationship("Answer", back_populates="question", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Question {self.type} #{self.order_index}>"
