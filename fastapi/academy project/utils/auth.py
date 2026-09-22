import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.db import users_db


SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
PBKDF2_ITERATIONS = 200_000

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
	salt = secrets.token_hex(16)
	digest = hashlib.pbkdf2_hmac(
		"sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
	)
	return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
	try:
		scheme, iterations, salt, expected = stored.split("$")
		if scheme != "pbkdf2_sha256":
			return False
		digest = hashlib.pbkdf2_hmac(
			"sha256",
			password.encode("utf-8"),
			salt.encode("utf-8"),
			int(iterations),
		)
		return secrets.compare_digest(digest.hex(), expected)
	except (ValueError, TypeError):
		return False


def create_access_token(user_id: int, email: str) -> str:
	now = datetime.now(timezone.utc)
	payload = {
		"sub": str(user_id),
		"email": email,
		"iat": now,
		"exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
	}
	return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
	return HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail=detail,
		headers={"WWW-Authenticate": "Bearer"},
	)


def get_current_user(
	credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
	if credentials is None or credentials.scheme.lower() != "bearer":
		raise _unauthorized("Not authenticated")

	try:
		payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
	except jwt.ExpiredSignatureError:
		raise _unauthorized("Token has expired")
	except jwt.InvalidTokenError:
		raise _unauthorized("Invalid token")

	try:
		user_id = int(payload["sub"])
	except (KeyError, TypeError, ValueError):
		raise _unauthorized("Invalid token")

	user = users_db.get(user_id)
	if user is None:
		raise _unauthorized("User not found")

	return {"id": user["id"], "email": user["email"]}
