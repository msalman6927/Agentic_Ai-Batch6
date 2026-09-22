from fastapi import APIRouter, HTTPException, status

from config.db import users_db
from models.schemas import TokenResponse, UserLogin, UserResponse, UserSignup
from utils.auth import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


def find_user_by_email(email: str) -> dict | None:
	for user in users_db.values():
		if user["email"] == email:
			return user
	return None


@router.post(
	"/signup",
	response_model=UserResponse,
	status_code=status.HTTP_201_CREATED,
)
def signup(payload: UserSignup) -> dict:
	if find_user_by_email(payload.email) is not None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="A user with this email already exists",
		)
	user_id = max(users_db, default=0) + 1
	users_db[user_id] = {
		"id": user_id,
		"email": payload.email,
		"password": hash_password(payload.password),
	}
	return users_db[user_id]


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin) -> dict:
	user = find_user_by_email(payload.email)
	if user is None or not verify_password(payload.password, user["password"]):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid email or password",
			headers={"WWW-Authenticate": "Bearer"},
		)
	token = create_access_token(user["id"], user["email"])
	return {"access_token": token, "token_type": "bearer"}
