import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, hash_token
from app.auth.models import LoginSession, User
from app.auth.schemas import AuthRequest, UserOut
from app.core.config import COOKIE_SECURE, SESSION_COOKIE, SESSION_DAYS
from app.core.database import get_db, utc_now

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
password_hasher = PasswordHasher()


async def create_login_session(response: Response, user: User, db: AsyncSession) -> None:
    token = secrets.token_urlsafe(32)
    max_age = SESSION_DAYS * 24 * 60 * 60
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utc_now() + timedelta(days=SESSION_DAYS),
        )
    )
    await db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: AuthRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    email = str(payload.email).lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=email, password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    await create_login_session(response, user, db)
    return user


@router.post("/login", response_model=UserOut)
async def login(
    payload: AuthRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    try:
        password_hasher.verify(user.password_hash, payload.password)
    except (InvalidHashError, VerifyMismatchError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from None

    await create_login_session(response, user, db)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> None:
    if token:
        await db.execute(delete(LoginSession).where(LoginSession.token_hash == hash_token(token)))
        await db.commit()
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> User:
    return user
