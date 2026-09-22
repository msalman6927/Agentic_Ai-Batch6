import re
from typing import Optional

from pydantic import BaseModel, Field, validator


PASSWORD_PATTERN = re.compile(
	r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$"
)


def validate_name(value: str) -> str:
	value = value.strip()
	if not value:
		raise ValueError("name cannot be empty")
	return value


def validate_gmail(value: str) -> str:
	value = value.strip().lower()
	if not value.endswith("@gmail.com") or value.count("@") != 1:
		raise ValueError("email must be a valid Gmail address")
	return value


def validate_password(value: str) -> str:
	if not PASSWORD_PATTERN.match(value):
		raise ValueError(
			"password must contain at least 8 characters, one uppercase letter, "
			"one lowercase letter, one digit, and one special character"
		)
	return value


def validate_text(value: str) -> str:
	value = value.strip()
	if not value:
		raise ValueError("value cannot be empty")
	return value


class StudentBase(BaseModel):
	name: str = Field(..., min_length=2, max_length=100)
	email: str = Field(..., min_length=7, max_length=254)

	_validate_name = validator("name", allow_reuse=True)(validate_name)
	_validate_email = validator("email", allow_reuse=True)(validate_gmail)


class StudentCreate(StudentBase):
	password: str = Field(..., min_length=8, max_length=128)

	_validate_password = validator("password", allow_reuse=True)(validate_password)


class StudentUpdate(StudentCreate):
	pass


class StudentPatch(BaseModel):
	name: Optional[str] = Field(None, min_length=2, max_length=100)
	email: Optional[str] = Field(None, min_length=7, max_length=254)
	password: Optional[str] = Field(None, min_length=8, max_length=128)

	_validate_name = validator("name", allow_reuse=True)(validate_name)
	_validate_email = validator("email", allow_reuse=True)(validate_gmail)
	_validate_password = validator("password", allow_reuse=True)(validate_password)


class StudentResponse(StudentBase):
	id: int


class CourseBase(BaseModel):
	title: str = Field(..., min_length=2, max_length=150)
	description: str = Field(..., min_length=5, max_length=2000)
	instructor: str = Field(..., min_length=2, max_length=100)

	_validate_title = validator("title", allow_reuse=True)(validate_text)
	_validate_description = validator("description", allow_reuse=True)(validate_text)
	_validate_instructor = validator("instructor", allow_reuse=True)(validate_text)


class CourseCreate(CourseBase):
	pass


class CourseUpdate(CourseBase):
	pass


class CoursePatch(BaseModel):
	title: Optional[str] = Field(None, min_length=2, max_length=150)
	description: Optional[str] = Field(None, min_length=5, max_length=2000)
	instructor: Optional[str] = Field(None, min_length=2, max_length=100)

	_validate_title = validator("title", allow_reuse=True)(validate_text)
	_validate_description = validator("description", allow_reuse=True)(validate_text)
	_validate_instructor = validator("instructor", allow_reuse=True)(validate_text)


class CourseResponse(CourseBase):
	id: int


class EnrollmentBase(BaseModel):
	student_id: int = Field(..., gt=0)
	course_id: int = Field(..., gt=0)


class EnrollmentCreate(EnrollmentBase):
	pass


class EnrollmentUpdate(EnrollmentBase):
	pass


class EnrollmentPatch(BaseModel):
	student_id: Optional[int] = Field(None, gt=0)
	course_id: Optional[int] = Field(None, gt=0)


class EnrollmentResponse(EnrollmentBase):
	id: int
