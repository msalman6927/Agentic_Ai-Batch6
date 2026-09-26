from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.schemas import (
	EnrollmentCreate,
	EnrollmentPatch,
	EnrollmentResponse,
	EnrollmentUpdate,
)
from models.tables import Course, Enrollment, Student
from utils.helpers import get_or_404


router = APIRouter(prefix="/enrollments", tags=["enrollments"])

_ALREADY_ENROLLED = "This student is already enrolled in this course"


async def validate_relationship(
	db: AsyncSession,
	student_id: int,
	course_id: int,
) -> None:
	await get_or_404(db, Student, student_id, "Student")
	await get_or_404(db, Course, course_id, "Course")


async def ensure_unique_enrollment(
	db: AsyncSession,
	student_id: int,
	course_id: int,
	excluded_id: int | None = None,
) -> None:
	stmt = select(Enrollment.id).where(
		Enrollment.student_id == student_id,
		Enrollment.course_id == course_id,
	)
	if excluded_id is not None:
		stmt = stmt.where(Enrollment.id != excluded_id)
	result = await db.execute(stmt)
	if result.scalar_one_or_none() is not None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=_ALREADY_ENROLLED,
		)


@router.post("", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
	enrollment: EnrollmentCreate,
	db: AsyncSession = Depends(get_db),
) -> Enrollment:
	await validate_relationship(db, enrollment.student_id, enrollment.course_id)
	await ensure_unique_enrollment(db, enrollment.student_id, enrollment.course_id)
	record = Enrollment(**enrollment.model_dump())
	db.add(record)
	await db.commit()
	await db.refresh(record)
	return record


@router.get("", response_model=list[EnrollmentResponse])
async def list_enrollments(db: AsyncSession = Depends(get_db)) -> list[Enrollment]:
	result = await db.execute(select(Enrollment).order_by(Enrollment.id))
	return list(result.scalars().all())


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
	enrollment_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Enrollment:
	return await get_or_404(db, Enrollment, enrollment_id, "Enrollment")


@router.put("/{enrollment_id}", response_model=EnrollmentResponse)
async def update_enrollment(
	enrollment: EnrollmentUpdate,
	enrollment_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Enrollment:
	record = await get_or_404(db, Enrollment, enrollment_id, "Enrollment")
	await validate_relationship(db, enrollment.student_id, enrollment.course_id)
	await ensure_unique_enrollment(
		db, enrollment.student_id, enrollment.course_id, enrollment_id
	)
	record.student_id = enrollment.student_id
	record.course_id = enrollment.course_id
	await db.commit()
	return record


@router.patch("/{enrollment_id}", response_model=EnrollmentResponse)
async def patch_enrollment(
	enrollment: EnrollmentPatch,
	enrollment_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Enrollment:
	record = await get_or_404(db, Enrollment, enrollment_id, "Enrollment")
	updates = enrollment.model_dump(exclude_unset=True)
	candidate_student_id = updates.get("student_id", record.student_id)
	candidate_course_id = updates.get("course_id", record.course_id)
	await validate_relationship(db, candidate_student_id, candidate_course_id)
	await ensure_unique_enrollment(
		db, candidate_student_id, candidate_course_id, enrollment_id
	)
	for field, value in updates.items():
		setattr(record, field, value)
	await db.commit()
	return record


@router.delete("/{enrollment_id}", response_model=EnrollmentResponse)
async def delete_enrollment(
	enrollment_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Enrollment:
	record = await get_or_404(db, Enrollment, enrollment_id, "Enrollment")
	await db.delete(record)
	await db.commit()
	return record
