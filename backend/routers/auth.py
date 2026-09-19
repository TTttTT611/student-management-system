from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..ratelimit import login_limiter
from ..security import (
    clear_session_cookie,
    client_ip,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.Token)
def login(data: schemas.LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request) or "unknown"
    keys = (f"user:{data.username}", f"ip:{ip}")
    remaining = max(login_limiter.locked_for(k) for k in keys)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts, try again in {max(1, remaining // 60)} minute(s)",
            headers={"Retry-After": str(remaining)},
        )

    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        for k in keys:
            login_limiter.record_failure(k)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    for k in keys:
        login_limiter.reset(k)
    token = create_access_token(user)
    set_session_cookie(response, token)
    return schemas.Token(access_token=token)


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    data: schemas.ChangePasswordIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from the current one")
    user.password_hash = hash_password(data.new_password)
    db.commit()


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(require_admin)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = models.User(
        username=data.username, password_hash=hash_password(data.password), role=data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/password", status_code=204)
def reset_password(
    user_id: int,
    data: schemas.ResetPasswordIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(data.new_password)
    db.commit()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_admin),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete the currently signed-in user")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
