"""
Nepal School Management System - Student Service
Student management business logic
"""

import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    DuplicateEMISError,
    StudentNotFoundError,
)
from services.student.models.student import (
    Student,
    StudentGuardian,
    StudentEnrollment,
    StudentStatus,
    EnrollmentStatus,
    Gender,
    CasteEthnicity,
    GuardianRelation,
)
from services.student.schemas.student import StudentCreate, StudentUpdate, GuardianCreate

logger = logging.getLogger(__name__)


class StudentService:
    """Student management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_student(
        self,
        data: StudentCreate,
        school_id: uuid.UUID,
        academic_year_bs: Optional[str] = None
    ) -> Student:
        """
        Create a new student with guardians and enrollment.

        Args:
            data: Student creation data
            school_id: School/tenant UUID
            academic_year_bs: Current academic year in BS

        Returns:
            Created Student object

        Raises:
            DuplicateEMISError: If EMIS ID already exists
        """
        # Check EMIS ID uniqueness
        if data.emis_student_id:
            result = await self.db.execute(
                select(Student).where(Student.emis_student_id == data.emis_student_id)
            )
            if result.scalar_one_or_none():
                raise DuplicateEMISError(data.emis_student_id)

        student = Student(
            id=uuid.uuid4(),
            school_id=school_id,
            emis_student_id=data.emis_student_id,
            admission_number=data.admission_number,
            roll_number=data.roll_number,
            full_name_en=data.full_name_en,
            full_name_np=data.full_name_np,
            gender=Gender(data.gender),
            date_of_birth_ad=data.date_of_birth_ad,
            date_of_birth_bs=data.date_of_birth_bs,
            phone=data.phone,
            email=data.email,
            address_permanent=data.address_permanent,
            address_temporary=data.address_temporary,
            current_grade=data.current_grade,
            current_section=data.current_section,
            current_faculty=data.current_faculty,
            admission_date_ad=data.admission_date_ad or datetime.utcnow().date(),
            admission_date_bs=data.admission_date_bs,
            caste_ethnicity=CasteEthnicity(data.caste_ethnicity) if data.caste_ethnicity else None,
            religion=data.religion,
            mother_tongue=data.mother_tongue,
            nationality=data.nationality,
            disability_type=data.disability_type,
            previous_school_name=data.previous_school_name,
            transfer_certificate_number=data.transfer_certificate_number,
            status=StudentStatus.ACTIVE,
        )

        self.db.add(student)

        # Add guardians
        for g_data in data.guardians:
            guardian = StudentGuardian(
                id=uuid.uuid4(),
                student_id=student.id,
                relation=GuardianRelation(g_data.relation),
                full_name_en=g_data.full_name_en,
                full_name_np=g_data.full_name_np,
                phone=g_data.phone,
                email=g_data.email,
                occupation=g_data.occupation,
                is_primary_contact=g_data.is_primary_contact,
            )
            self.db.add(guardian)

        # Create enrollment record
        if academic_year_bs:
            enrollment = StudentEnrollment(
                id=uuid.uuid4(),
                student_id=student.id,
                school_id=school_id,
                academic_year_bs=academic_year_bs,
                grade=data.current_grade,
                section=data.current_section,
                faculty=data.current_faculty,
                roll_number=data.roll_number,
                status=EnrollmentStatus.ENROLLED,
                enrolled_at=datetime.utcnow(),
            )
            self.db.add(enrollment)

        await self.db.commit()
        await self.db.refresh(student)

        logger.info(f"Student created: {student.full_name_en} (ID: {student.id})")
        return student

    async def get_student(self, student_id: uuid.UUID) -> Student:
        """Get student by ID with guardians"""
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id, Student.deleted_at.is_(None))
            .options(selectinload(Student.guardians))
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(str(student_id))

        return student

    async def update_student(self, student_id: uuid.UUID, data: StudentUpdate) -> Student:
        """Update student details"""
        student = await self.get_student(student_id)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if value is not None:
                if field == "status":
                    setattr(student, field, StudentStatus(value))
                else:
                    setattr(student, field, value)

        await self.db.commit()
        await self.db.refresh(student)

        logger.info(f"Student updated: {student.full_name_en}")
        return student

    async def delete_student(self, student_id: uuid.UUID):
        """Soft delete student"""
        student = await self.get_student(student_id)
        student.deleted_at = datetime.utcnow()
        student.status = StudentStatus.INACTIVE

        await self.db.commit()
        logger.info(f"Student soft-deleted: {student.full_name_en}")

    async def list_students(
        self,
        school_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        grade: Optional[int] = None,
        section: Optional[str] = None,
        status_filter: Optional[StudentStatus] = None,
    ) -> Tuple[List[Student], int]:
        """List students with pagination and filters"""
        query = select(Student).where(
            Student.school_id == school_id,
            Student.deleted_at.is_(None)
        )

        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Student.full_name_en.ilike(pattern)) |
                (Student.full_name_np.ilike(pattern)) |
                (Student.emis_student_id.ilike(pattern)) |
                (Student.admission_number.ilike(pattern))
            )

        if grade:
            query = query.where(Student.current_grade == grade)

        if section:
            query = query.where(Student.current_section == section)

        if status_filter:
            query = query.where(Student.status == status_filter)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        query = query.options(selectinload(Student.guardians))
        query = query.order_by(Student.current_grade, Student.roll_number, Student.full_name_en)

        result = await self.db.execute(query)
        students = result.scalars().all()

        return students, total

    async def search_students(
        self,
        school_id: uuid.UUID,
        query_str: str,
        limit: int = 10
    ) -> List[Student]:
        """Quick search for students by name or ID"""
        pattern = f"%{query_str}%"
        query = (
            select(Student)
            .where(
                Student.school_id == school_id,
                Student.deleted_at.is_(None),
                (Student.full_name_en.ilike(pattern)) |
                (Student.full_name_np.ilike(pattern)) |
                (Student.emis_student_id.ilike(pattern)) |
                (Student.admission_number.ilike(pattern))
            )
            .limit(limit)
            .options(selectinload(Student.guardians))
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def bulk_import(
        self,
        school_id: uuid.UUID,
        students_data: List[dict],
        academic_year_bs: Optional[str] = None
    ) -> dict:
        """
        Bulk import students from CSV/Excel data.

        Args:
            school_id: School UUID
            students_data: List of student data dictionaries
            academic_year_bs: Academic year

        Returns:
            Import result summary
        """
        imported = 0
        failed = 0
        errors = []

        for i, row in enumerate(students_data):
            try:
                student_data = StudentCreate(**row)
                await self.create_student(student_data, school_id, academic_year_bs)
                imported += 1
            except Exception as e:
                failed += 1
                errors.append({
                    "row": i + 1,
                    "error": str(e),
                    "data": row.get("full_name_en", "Unknown"),
                })

        await self.db.commit()

        logger.info(f"Bulk import complete: {imported} imported, {failed} failed")
        return {
            "total_rows": len(students_data),
            "imported": imported,
            "failed": failed,
            "errors": errors[:50],  # Limit error details
        }

    async def get_enrollment_history(self, student_id: uuid.UUID) -> List[StudentEnrollment]:
        """Get enrollment history for a student"""
        result = await self.db.execute(
            select(StudentEnrollment)
            .where(StudentEnrollment.student_id == student_id)
            .order_by(StudentEnrollment.academic_year_bs.desc())
        )
        return result.scalars().all()
