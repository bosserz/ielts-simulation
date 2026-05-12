"""
Database seed script — creates a sample exam and users for development.

Usage:
    python seed.py
"""
import bcrypt
from dotenv import load_dotenv
load_dotenv()  # load DATABASE_URL and other vars from .env before create_app reads them

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole
from app.models.exam import Exam, Section, Question, ExamType, ExamStatus, SectionType, QuestionType
from app.models.session import ExamSession, SessionStatus


def seed():
    app = create_app("development")
    with app.app_context():
        db.create_all()

        # Create admin user
        if not User.query.filter_by(email="admin@intsight.com").first():
            admin = User(
                name="Admin Teacher",
                email="admin@intsight.com",
                password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
                role=UserRole.ADMIN,
            )
            db.session.add(admin)
            db.session.flush()

        # Create a test student
        if not User.query.filter_by(email="student@test.com").first():
            student = User(
                name="Test Student",
                email="student@test.com",
                password_hash=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
                role=UserRole.STUDENT,
                target_score=7.0,
            )
            db.session.add(student)

        db.session.flush()
        admin = User.query.filter_by(email="admin@intsight.com").first()

        # Create a sample exam
        if not Exam.query.filter_by(title="Sample Academic Test 1").first():
            exam = Exam(
                title="Sample Academic Test 1",
                type=ExamType.ACADEMIC,
                status=ExamStatus.PUBLISHED,
                created_by=admin.id,
            )
            db.session.add(exam)
            db.session.flush()

            # Listening section
            listening = Section(
                exam_id=exam.id,
                type=SectionType.LISTENING,
                order_index=1,
                time_limit_s=30 * 60,  # 30 minutes
                config={
                    "audioFileKey": "samples/listening-sample-1.mp3",
                },
            )
            db.session.add(listening)
            db.session.flush()

            for i in range(1, 5):
                q = Question(
                    section_id=listening.id,
                    order_index=i,
                    type=QuestionType.MCQ,
                    prompt=f"Sample listening question {i}. What does the speaker mention?",
                    options=[
                        {"id": "A", "text": "Option A"},
                        {"id": "B", "text": "Option B"},
                        {"id": "C", "text": "Option C"},
                    ],
                    correct_answer="A",
                    group_id="listening-part1",
                )
                db.session.add(q)

            # Reading section
            reading = Section(
                exam_id=exam.id,
                type=SectionType.READING,
                order_index=2,
                time_limit_s=60 * 60,  # 60 minutes
                config={
                    "passageText": (
                        "<h3>The History of Coffee</h3>"
                        "<p>Coffee, one of the world's most popular beverages, has a rich history "
                        "spanning centuries. Its origins can be traced to the ancient coffee forests "
                        "of Ethiopia, where legend has it that a goat herder named Kaldi first "
                        "discovered the potential of these beloved beans around 850 CE.</p>"
                        "<p>From Ethiopia, knowledge of the coffee plant spread to the Arabian "
                        "Peninsula, where it was first cultivated in Yemen. By the 15th century, "
                        "coffee was being grown in the Yemeni district of Arabia, and by the "
                        "16th century it was widely known across the Middle East, Persia, Turkey "
                        "and North Africa.</p>"
                    ),
                },
            )
            db.session.add(reading)
            db.session.flush()

            tfng_questions = [
                ("Coffee originated in Ethiopia.", "True"),
                ("Kaldi was a farmer.", "Not Given"),
                ("Coffee reached Europe before the Arabian Peninsula.", "False"),
            ]
            for i, (prompt, answer) in enumerate(tfng_questions, start=1):
                q = Question(
                    section_id=reading.id,
                    order_index=i,
                    type=QuestionType.TFNG,
                    prompt=prompt,
                    correct_answer=answer,
                    group_id="reading-passage1",
                )
                db.session.add(q)

        db.session.commit()
        print("Seed complete.")
        print("  Admin:   admin@intsight.com / password123")
        print("  Student: student@test.com   / password123")


if __name__ == "__main__":
    seed()
