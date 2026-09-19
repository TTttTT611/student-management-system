from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _group(db: Session, column, unknown_label: str) -> list[schemas.CountItem]:
    rows = (
        db.query(column, func.count(models.Student.id))
        .group_by(column)
        .order_by(func.count(models.Student.id).desc())
        .all()
    )
    return [schemas.CountItem(label=label or unknown_label, count=n) for label, n in rows]


@router.get("", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    by_class_rows = (
        db.query(models.Clazz.name, func.count(models.Student.id))
        .outerjoin(models.Student, models.Student.class_id == models.Clazz.id)
        .group_by(models.Clazz.id)
        .order_by(func.count(models.Student.id).desc())
        .all()
    )
    unassigned = db.query(func.count(models.Student.id)).filter(models.Student.class_id.is_(None)).scalar()
    by_class = [schemas.CountItem(label=name, count=n) for name, n in by_class_rows]
    if unassigned:
        by_class.append(schemas.CountItem(label="Unassigned", count=unassigned))

    return schemas.StatsOut(
        total_students=db.query(func.count(models.Student.id)).scalar(),
        total_classes=db.query(func.count(models.Clazz.id)).scalar(),
        total_courses=db.query(func.count(models.Course.id)).scalar(),
        by_major=_group(db, models.Student.major, "Unspecified"),
        by_gender=_group(db, models.Student.gender, "Unknown"),
        by_class=by_class,
    )
