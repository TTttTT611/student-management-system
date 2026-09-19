from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")

Gender = Literal["male", "female"]
Role = Literal["admin", "user"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


# ---------- auth ----------
def _check_bcrypt_len(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return v


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50, pattern=r"^\S+$")
    password: str = Field(min_length=6, max_length=72)
    role: Role = "user"

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, v: str) -> str:
        # bcrypt only hashes the first 72 bytes; multi-byte characters reach the limit sooner
        return _check_bcrypt_len(v)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=6, max_length=72)

    _len = field_validator("new_password")(_check_bcrypt_len)


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=72)

    _len = field_validator("new_password")(_check_bcrypt_len)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    user_id: int | None
    username: str | None
    ip: str | None
    method: str
    path: str
    status: int
    detail: str | None


# ---------- class ----------
class ClassBase(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^\S.*$")
    major: str | None = Field(default=None, max_length=100)


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50, pattern=r"^\S.*$")
    major: str | None = Field(default=None, max_length=100)


class ClassOut(ClassBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_count: int = 0


# ---------- student ----------
class StudentBase(BaseModel):
    name: str = Field(min_length=1, max_length=50, pattern=r"^\S.*$")
    age: int = Field(ge=1, le=150)
    gender: Gender
    student_no: str = Field(min_length=1, max_length=20, pattern=r"^\S+$")
    major: str | None = Field(default=None, max_length=100)
    class_id: int | None = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50, pattern=r"^\S.*$")
    age: int | None = Field(default=None, ge=1, le=150)
    gender: Gender | None = None
    major: str | None = Field(default=None, max_length=100)
    student_no: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^\S+$")
    class_id: int | None = None


class StudentOut(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_name: str | None = None


# ---------- course ----------
class CourseBase(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^\S+$")
    name: str = Field(min_length=1, max_length=100, pattern=r"^\S.*$")
    credit: float = Field(ge=0, le=20)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^\S+$")
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^\S.*$")
    credit: float | None = Field(default=None, ge=0, le=20)


class CourseOut(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------- enrollment / grade ----------
class EnrollmentCreate(BaseModel):
    student_id: int
    course_id: int
    score: float | None = Field(default=None, ge=0, le=100)


class ScoreUpdate(BaseModel):
    score: float | None = Field(default=None, ge=0, le=100)


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_id: int
    score: float | None
    student_name: str
    student_no: str
    course_name: str
    course_code: str
    credit: float


# ---------- stats ----------
class CountItem(BaseModel):
    label: str
    count: int


class StatsOut(BaseModel):
    total_students: int
    total_classes: int
    total_courses: int
    by_major: list[CountItem]
    by_gender: list[CountItem]
    by_class: list[CountItem]
