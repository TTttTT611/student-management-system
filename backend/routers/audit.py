from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import require_admin

router = APIRouter(prefix="/audit-logs", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("", response_model=schemas.Page[schemas.AuditLogOut])
def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    username: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db),
):
    q = db.query(models.AuditLog)
    if username:
        q = q.filter(models.AuditLog.username == username.strip())
    total = q.count()
    items = q.order_by(models.AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return schemas.Page(items=items, total=total, page=page, size=size)
