from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.schemas import CourseCreate, CoursePatch, CourseResponse, CourseUpdate
from models.tables import Course, Enrollment
from utils.helpers import get_or_404


router = APIRouter(prefix="/courses", tags=["courses"])

_ENROLLMENT_CONFLICT = "Cannot delete a course with active enrollments"


async def has_enrollments(db: AsyncSession, course_id: int) -> bool:
	result = await db.execute(
		select(Enrollment.id).where(Enrollment.course_id == course_id).limit(1)
	)
	return result.scalar_one_or_none() is not None


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
	course: CourseCreate,
	db: AsyncSession = Depends(get_db),
) -> Course:
	record = Course(**course.model_dump())
	db.add(record)
	await db.commit()
	await db.refresh(record)
	return record


@router.get("", response_model=list[CourseResponse])
async def list_courses(db: AsyncSession = Depends(get_db)) -> list[Course]:
	result = await db.execute(select(Course).order_by(Course.id))
	return list(result.scalars().all())


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
	course_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Course:
	return await get_or_404(db, Course, course_id, "Course")


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
	course: CourseUpdate,
	course_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Course:
	record = await get_or_404(db, Course, course_id, "Course")
	data = course.model_dump()
	for field, value in data.items():
		setattr(record, field, value)
	await db.commit()
	return record


@router.patch("/{course_id}", response_model=CourseResponse)
async def patch_course(
	course: CoursePatch,
	course_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Course:
	record = await get_or_404(db, Course, course_id, "Course")
	for field, value in course.model_dump(exclude_unset=True).items():
		setattr(record, field, value)
	await db.commit()
	return record


@router.delete("/{course_id}", response_model=CourseResponse)
async def delete_course(
	course_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Course:
	record = await get_or_404(db, Course, course_id, "Course")
	if await has_enrollments(db, course_id):
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=_ENROLLMENT_CONFLICT,
		)
	await db.delete(record)
	try:
		await db.commit()
	except IntegrityError:
		await db.rollback()
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=_ENROLLMENT_CONFLICT,
		)
	return record
