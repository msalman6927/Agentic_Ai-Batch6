from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.schemas import TokenResponse, UserLogin, UserResponse, UserSignup
from models.tables import User
from utils.auth import create_access_token, hash_password, verify_password
from utils.helpers import ensure_email_available


router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_CONFLICT = "A user with this email already exists"
_INVALID_CREDENTIALS = "Invalid email or password"


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
	result = await db.execute(select(User).where(User.email == email))
	return result.scalar_one_or_none()


@router.post(
	"/signup",
	response_model=UserResponse,
	status_code=status.HTTP_201_CREATED,
)
async def signup(payload: UserSignup, db: AsyncSession = Depends(get_db)) -> User:
	await ensure_email_available(db, User, payload.email, _EMAIL_CONFLICT)
	hashed_password = await run_in_threadpool(hash_password, payload.password)
	record = User(email=payload.email, password=hashed_password)
	db.add(record)
	await db.commit()
	await db.refresh(record)
	return record


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> dict:
	user = await find_user_by_email(db, payload.email)
	valid = False
	if user is not None:
		valid = await run_in_threadpool(verify_password, payload.password, user.password)
	if not valid:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=_INVALID_CREDENTIALS,
			headers={"WWW-Authenticate": "Bearer"},
		)
	token = create_access_token(user.id, user.email)
	return {"access_token": token, "token_type": "bearer"}
