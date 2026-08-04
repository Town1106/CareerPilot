import hashlib

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginSession, User
from app.core.config import SESSION_COOKIE
from app.core.database import get_db, utc_now


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    user = await db.scalar(
        select(User)
        .join(LoginSession, LoginSession.user_id == User.id)
        .where(
            LoginSession.token_hash == hash_token(token),
            LoginSession.expires_at > utc_now(),
        )
    )
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    return user
