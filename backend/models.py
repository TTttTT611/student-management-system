from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # admin / user


class Clazz(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    major = Column(String(100), nullable=True)

    students = relationship("Student", back_populates="clazz")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, index=True)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    student_no = Column(String(20), unique=True, nullable=False, index=True)
    major = Column(String(100), nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)

    clazz = relationship("Clazz", back_populates="students")
    enrollments = relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    credit = Column(Float, nullable=False, default=0)

    enrollments = relationship(
        "Enrollment", back_populates="course", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    """A student's enrollment in a course; score is None until graded."""

    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=True)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class AuditLog(Base):
    """Audit log: every write request and login attempt."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True
    )
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=True, index=True)
    ip = Column(String(45), nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    status = Column(Integer, nullable=False)
    detail = Column(Text, nullable=True)
