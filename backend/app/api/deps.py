# app/api/deps.py
"""Shared dependency untuk semua endpoint v1."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import JWTError, decode_access_token
from app.db.session import get_session

# tokenUrl cuma dipakai untuk generate dokumentasi Swagger "Authorize" button
# (endpoint /auth/login belum dibuat — akan disambungkan begitu ada)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency FastAPI standar: `db: AsyncSession = Depends(get_db)`.

    Commit/rollback/close sudah ditangani di db.session.get_session — di
    sini TIDAK boleh ditambah commit/rollback lagi supaya tidak dobel
    transaksi per request.
    """
    async for session in get_session():
        yield session


class CurrentUser(BaseModel):
    """
    Payload user hasil decode JWT. Sengaja TIDAK query ke DB di sini —
    begitu modul auth/user punya tabel sendiri, tambahkan lookup
    `user_id -> UserRecord` di dalam get_current_user kalau perlu data
    lain (mis. role, factory_id yang di-assign).
    """

    user_id: str
    raw_claims: dict


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kredensial tidak valid atau sudah kedaluwarsa.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_error

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    return CurrentUser(user_id=user_id, raw_claims=payload)