import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from ..extensions import db, login_manager


class UserRole:
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class User(UserMixin, db.Model):
    __tablename__ = "ielts_users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.STUDENT)
    target_score = db.Column(db.Numeric(5, 1), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    sessions = db.relationship("ExamSession", back_populates="user", lazy="dynamic")
    created_exams = db.relationship("Exam", back_populates="creator", lazy="dynamic")

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role in (UserRole.TEACHER, UserRole.ADMIN)

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, user_id)
