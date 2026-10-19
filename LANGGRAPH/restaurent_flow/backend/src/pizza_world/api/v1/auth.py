from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from pizza_world.core.security import (
    AnyUser,
    create_access_token,
    hash_password,
    verify_password,
)
from pizza_world.db.models import User
from pizza_world.db.session import get_session_maker

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    name: str


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn) -> TokenOut:
    async with get_session_maker()() as session:
        existing = (
            await session.execute(select(User).where(User.email == body.email))
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        user = User(
            name=body.name,
            email=body.email,
            password_hash=hash_password(body.password),
            role="user",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, role=user.role, user_id=user.id, name=user.name)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn) -> TokenOut:
    async with get_session_maker()() as session:
        user = (
            await session.execute(select(User).where(User.email == body.email))
        ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, role=user.role, user_id=user.id, name=user.name)


@router.get("/me")
async def me(user: AnyUser) -> dict[str, str]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
