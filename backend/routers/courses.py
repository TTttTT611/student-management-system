from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/courses", tags=["courses"], dependencies=[Depends(get_current_user)])


def _get_or_404(db: Session, course_id: int) -> models.Course:
    course = db.get(models.Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("", response_model=list[schemas.CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return db.query(models.Course).order_by(models.Course.id).all()


@router.get("/{course_id}", response_model=schemas.CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, course_id)


@router.post("", response_model=schemas.CourseOut, status_code=201, dependencies=[Depends(require_admin)])
def create_course(data: schemas.CourseCreate, db: Session = Depends(get_db)):
    if db.query(models.Course).filter(models.Course.code == data.code).first():
        raise HTTPException(status_code=400, detail="Course code already exists")
    course = models.Course(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.put("/{course_id}", response_model=schemas.CourseOut, dependencies=[Depends(require_admin)])
def update_course(course_id: int, data: schemas.CourseUpdate, db: Session = Depends(get_db)):
    course = _get_or_404(db, course_id)
    changes = data.model_dump(exclude_unset=True)
    new_code = changes.get("code")
    if new_code and new_code != course.code:
        if db.query(models.Course).filter(models.Course.code == new_code).first():
            raise HTTPException(status_code=400, detail="Course code already exists")
    for k, v in changes.items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_course(course_id: int, db: Session = Depends(get_db)):
    course = _get_or_404(db, course_id)
    db.delete(course)
    db.commit()
