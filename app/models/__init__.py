# Import all models here so Flask-Migrate discovers them automatically
from .user import User
from .exam import Exam, Section, Question
from .session import ExamSession, Answer
from .response import WritingResponse, SpeakingResponse
from .score import Score
from .annotation import Annotation

__all__ = [
    "User",
    "Exam", "Section", "Question",
    "ExamSession", "Answer",
    "WritingResponse", "SpeakingResponse",
    "Score",
    "Annotation",
]
