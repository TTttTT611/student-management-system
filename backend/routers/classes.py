from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/classes", tags=["classes"], dependencies=[Depends(get_current_user)])


def _to_out(clazz: models.Clazz, count: int) -> schemas.ClassOut:
    return schemas.ClassOut(id=clazz.id, name=clazz.name, major=clazz.major, student_count=count)


def _get_or_404(db: Session, class_id: int) -> models.Clazz:
    clazz = db.get(models.Clazz, class_id)
    if not clazz:
        raise HTTPException(status_code=404, detail="Class not found")
    return clazz


def _count(db: Session, class_id: int) -> int:
    return db.query(func.count(models.Student.id)).filter(models.Student.class_id == class_id).scalar()


@router.get("", response_model=list[schemas.ClassOut])
def list_classes(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Clazz, func.count(models.Student.id))
        .outerjoin(models.Student, models.Student.class_id == models.Clazz.id)
        .group_by(models.Clazz.id)
        .order_by(models.Clazz.id)
        .all()
    )
    return [_to_out(c, n) for c, n in rows]


@router.get("/{class_id}", response_model=schemas.ClassOut)
def get_class(class_id: int, db: Session = Depends(get_db)):
    clazz = _get_or_404(db, class_id)
    return _to_out(clazz, _count(db, class_id))


@router.post("", response_model=schemas.ClassOut, status_code=201, dependencies=[Depends(require_admin)])
def create_class(data: schemas.ClassCreate, db: Session = Depends(get_db)):
    if db.query(models.Clazz).filter(models.Clazz.name == data.name).first():
        raise HTTPException(status_code=400, detail="Class name already exists")
    clazz = models.Clazz(**data.model_dump())
    db.add(clazz)
    db.commit()
    db.refresh(clazz)
    return _to_out(clazz, 0)


@router.put("/{class_id}", response_model=schemas.ClassOut, dependencies=[Depends(require_admin)])
def update_class(class_id: int, data: schemas.ClassUpdate, db: Session = Depends(get_db)):
    clazz = _get_or_404(db, class_id)
    changes = data.model_dump(exclude_unset=True)
    new_name = changes.get("name")
    if new_name and new_name != clazz.name:
        if db.query(models.Clazz).filter(models.Clazz.name == new_name).first():
            raise HTTPException(status_code=400, detail="Class name already exists")
    for k, v in changes.items():
        setattr(clazz, k, v)
    db.commit()
    db.refresh(clazz)
    return _to_out(clazz, _count(db, class_id))


@router.delete("/{class_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_class(class_id: int, db: Session = Depends(get_db)):
    clazz = _get_or_404(db, class_id)
    # Detach students from the class instead of deleting them
    db.query(models.Student).filter(models.Student.class_id == class_id).update({"class_id": None})
    db.delete(clazz)
    db.commit()
