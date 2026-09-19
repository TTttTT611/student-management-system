from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/enrollments", tags=["enrollments"], dependencies=[Depends(get_current_user)])


def _to_out(e: models.Enrollment) -> schemas.EnrollmentOut:
    return schemas.EnrollmentOut(
        id=e.id,
        student_id=e.student_id,
        course_id=e.course_id,
        score=e.score,
        student_name=e.student.name,
        student_no=e.student.student_no,
        course_name=e.course.name,
        course_code=e.course.code,
        credit=e.course.credit,
    )


def _base_query(db: Session):
    return db.query(models.Enrollment).options(
        joinedload(models.Enrollment.student), joinedload(models.Enrollment.course)
    )


@router.get("", response_model=list[schemas.EnrollmentOut])
def list_enrollments(
    student_id: int | None = None,
    course_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = _base_query(db)
    if student_id is not None:
        q = q.filter(models.Enrollment.student_id == student_id)
    if course_id is not None:
        q = q.filter(models.Enrollment.course_id == course_id)
    return [_to_out(e) for e in q.order_by(models.Enrollment.id).all()]


@router.post("", response_model=schemas.EnrollmentOut, status_code=201, dependencies=[Depends(require_admin)])
def create_enrollment(data: schemas.EnrollmentCreate, db: Session = Depends(get_db)):
    if db.get(models.Student, data.student_id) is None:
        raise HTTPException(status_code=400, detail="Student not found")
    if db.get(models.Course, data.course_id) is None:
        raise HTTPException(status_code=400, detail="Course not found")
    dup = (
        db.query(models.Enrollment)
        .filter(
            models.Enrollment.student_id == data.student_id,
            models.Enrollment.course_id == data.course_id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="Student is already enrolled in this course")
    e = models.Enrollment(**data.model_dump())
    db.add(e)
    db.commit()
    return _to_out(_base_query(db).filter(models.Enrollment.id == e.id).one())


@router.put("/{enrollment_id}", response_model=schemas.EnrollmentOut, dependencies=[Depends(require_admin)])
def update_score(enrollment_id: int, data: schemas.ScoreUpdate, db: Session = Depends(get_db)):
    e = _base_query(db).filter(models.Enrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    e.score = data.score
    db.commit()
    db.refresh(e)
    return _to_out(e)


@router.delete("/{enrollment_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
    e = db.get(models.Enrollment, enrollment_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(e)
    db.commit()
