"""Request dependencies: database session and authenticated user."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.models import User, UserSession


def current_session(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> UserSession:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    session = db.scalar(
        select(UserSession)
        .where(UserSession.token_hash == hash_token(token))
        .options(joinedload(UserSession.user).joinedload(User.organization))
    )
    if session is None or session.expires_at <= datetime.now(UTC) or not session.user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid.")
    return session


def current_user(session: UserSession = Depends(current_session)) -> User:
    return session.user
