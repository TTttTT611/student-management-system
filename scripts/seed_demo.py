"""Generate demo / load-test data.

Usage (from the project root, after `alembic upgrade head`):
    python scripts/seed_demo.py            # 5000 students by default
    python scripts/seed_demo.py 20000
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import models  # noqa: E402
from backend.database import SessionLocal  # noqa: E402

MAJORS = {
    "Computer Science": "CS",
    "Software Engineering": "SE",
    "Mathematics": "MATH",
    "Physics": "PHYS",
    "English": "ENG",
    "Economics": "ECON",
    "Mechanical Engineering": "ME",
    "Automation": "AUTO",
}
FIRST_NAMES = ["Alice", "Bob", "Carol", "Dan", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack", "Kate", "Leo", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Ruby", "Sam", "Tina"]
LAST_NAMES = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Martin", "Jackson", "White", "Harris", "Clark", "Lewis", "Walker", "Young"]


def main(n: int) -> None:
    db = SessionLocal()
    try:
        if db.query(models.Student).count():
            print("students table is not empty, skipping (clear it first to regenerate)")
            return

        classes = [models.Clazz(name=f"{abbr}-{i}", major=major) for major, abbr in MAJORS.items() for i in (1, 2, 3)]
        db.add_all(classes)
        courses = [
            models.Course(code=f"C{i:03d}", name=f"Course {i}", credit=random.choice([1, 2, 3, 4]))
            for i in range(1, 41)
        ]
        db.add_all(courses)
        db.flush()

        rnd = random.Random(42)
        students = []
        for i in range(1, n + 1):
            c = rnd.choice(classes)
            students.append(
                models.Student(
                    name=f"{rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}",
                    age=rnd.randint(17, 25),
                    gender=rnd.choice(["male", "female"]),
                    student_no=f"2024{i:06d}",
                    major=c.major,
                    class_id=c.id,
                )
            )
        db.bulk_save_objects(students, return_defaults=False)
        db.flush()

        ids = [sid for (sid,) in db.query(models.Student.id).all()]
        enrollments = []
        for sid in ids:
            for course in rnd.sample(courses, 5):
                enrollments.append(
                    models.Enrollment(student_id=sid, course_id=course.id, score=rnd.choice([None, rnd.randint(40, 100)]))
                )
        db.bulk_save_objects(enrollments)
        db.commit()
        print(f"Created {len(classes)} classes, {len(courses)} courses, {n} students, {len(enrollments)} enrollments")
    finally:
        db.close()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5000)
