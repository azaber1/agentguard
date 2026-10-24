"""Registration, login, logout and current user."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_session, current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import (
    dummy_verify,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from app.db.session import get_db
from app.models import Organization, User, UserSession
from app.schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = RateLimiter(limit=get_settings().login_rate_limit_per_minute)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _start_session(
    db: Session, user: User, request: Request, response: Response, settings: Settings
) -> None:
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires,
            user_agent=(request.headers.get("user-agent") or "")[:300],
        )
    )
    user.last_login_at = datetime.now(UTC)
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not settings.allow_registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is disabled.")
    if not login_limiter.allow(f"register:{_client_ip(request)}"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again shortly."
        )
    email = body.email.lower()
    if db.scalar(select(func.count()).select_from(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    org = Organization(name=body.organization_name.strip())
    user = User(
        organization=org,
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="admin",
    )
    db.add_all([org, user])
    db.flush()
    _start_session(db, user, request, response, settings)
    return user


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    email = body.email.lower()
    if not login_limiter.allow(f"login:{_client_ip(request)}:{email}"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Try again in a minute."
        )
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        dummy_verify()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    if not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")
    _start_session(db, user, request, response, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: UserSession = Depends(current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    db.delete(session)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.get("/config")
def auth_config(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    return {"allow_registration": settings.allow_registration}
