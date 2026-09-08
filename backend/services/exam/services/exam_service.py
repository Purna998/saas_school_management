"""
Nepal School Management System - Exam Service
Business logic for exam management, marks entry, and result calculation

Grading Systems:
- Grades 1-10: GPA system (4.0 scale)
- Grades 11-12: Percentage with division system
"""

import uuid
import logging
from typing import Optional, List, Tuple
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import RecordNotFoundError
from services.exam.models.exam import (
    Exam,
    ExamSubject,
    Mark,
    Result,
    ExamType,
    ExamStatus,
    ResultStatus,
    Division,
)
from services.exam.schemas.exam import (
    ExamCreate,
    ExamStatusUpdate,
    MarkEntryRequest,
    MarkEntry,
)

logger = logging.getLogger(__name__)


# GPA Conversion Table (Nepal, Grades 1-10)
# Percentage range -> Grade Point
GPA_TABLE = [
    (90, 100, Decimal("4.0")),
    (80, 89, Decimal("3.6")),
    (70, 79, Decimal("3.2")),
    (60, 69, Decimal("2.8")),
    (50, 59, Decimal("2.4")),
    (40, 49, Decimal("2.0")),
    (0, 39, Decimal("0.0")),
]


def calculate_grade_point(marks_obtained: Decimal, full_marks: Decimal) -> Decimal:
    """
    Calculate grade point from marks using Nepal GPA table.

    Args:
        marks_obtained: Marks scored by student
        full_marks: Maximum possible marks

    Returns:
        Grade point on 4.0 scale
    """
    if full_marks <= 0:
        return Decimal("0.0")

    percentage = (marks_obtained / full_marks) * 100

    for low, high, gp in GPA_TABLE:
        if low <= percentage <= high:
            return gp

    return Decimal("0.0")


def calculate_division(percentage: Decimal) -> Division:
    """
    Calculate division for Higher Secondary (Grades 11-12).

    Args:
        percentage: Overall percentage

    Returns:
        Division enum value
    """
    if percentage >= 60:
        return Division.FIRST
    elif percentage >= 45:
        return Division.SECOND
    elif percentage >= 32:
        return Division.THIRD
    else:
        return Division.FAIL


class ExamService:
    """Exam management service with Nepal-specific grading"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Exam CRUD
    # ============================================================

    async def create_exam(self, data: ExamCreate, school_id: uuid.UUID) -> Exam:
        """
        Create a new exam with subject configurations.

        Args:
            data: Exam creation data including subjects
            school_id: School/tenant UUID

        Returns:
            Created Exam object with subjects loaded
        """
        exam = Exam(
            id=uuid.uuid4(),
            school_id=school_id,
            name=data.name,
            exam_type=ExamType(data.exam_type),
            academic_year_bs=data.academic_year_bs,
            grade=data.grade,
            start_date_ad=data.start_date_ad,
            end_date_ad=data.end_date_ad,
            status=ExamStatus.DRAFT,
            is_locked=False,
        )
        self.db.add(exam)

        # Add exam subjects
        for subject_data in data.subjects:
            exam_subject = ExamSubject(
                id=uuid.uuid4(),
                exam_id=exam.id,
                subject_id=subject_data.subject_id,
                full_marks=subject_data.full_marks,
                pass_marks=subject_data.pass_marks,
                exam_date_ad=subject_data.exam_date_ad,
                start_time=subject_data.start_time,
                end_time=subject_data.end_time,
            )
            self.db.add(exam_subject)

        await self.db.commit()
        await self.db.refresh(exam)

        # Reload with relationships
        return await self.get_exam(exam.id)

    async def get_exam(self, exam_id: uuid.UUID) -> Exam:
        """
        Get exam by ID with subjects loaded.

        Args:
            exam_id: Exam UUID

        Returns:
            Exam object with subjects

        Raises:
            RecordNotFoundError: If exam not found
        """
        result = await self.db.execute(
            select(Exam)
            .where(Exam.id == exam_id, Exam.deleted_at.is_(None))
            .options(selectinload(Exam.subjects))
        )
        exam = result.scalar_one_or_none()

        if not exam:
            raise RecordNotFoundError(f"Exam with ID {exam_id} not found")

        return exam

    async def list_exams(
        self,
        school_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        grade: Optional[int] = None,
        academic_year_bs: Optional[str] = None,
        exam_type: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[Exam], int]:
        """
        List exams with pagination and filters.

        Args:
            school_id: School/tenant UUID
            page: Page number (1-based)
            limit: Items per page
            grade: Filter by grade
            academic_year_bs: Filter by academic year
            exam_type: Filter by exam type
            status_filter: Filter by status

        Returns:
            Tuple of (exams list, total count)
        """
        query = select(Exam).where(
            Exam.school_id == school_id,
            Exam.deleted_at.is_(None),
        )

        if grade:
            query = query.where(Exam.grade == grade)

        if academic_year_bs:
            query = query.where(Exam.academic_year_bs == academic_year_bs)

        if exam_type:
            query = query.where(Exam.exam_type == ExamType(exam_type))

        if status_filter:
            query = query.where(Exam.status == ExamStatus(status_filter))

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * limit
        query = (
            query
            .offset(offset)
            .limit(limit)
            .options(selectinload(Exam.subjects))
            .order_by(Exam.created_at.desc())
        )

        result = await self.db.execute(query)
        exams = result.scalars().all()

        return exams, total

    async def update_exam_status(
        self,
        exam_id: uuid.UUID,
        data: ExamStatusUpdate
    ) -> Exam:
        """
        Update exam status with validation.

        Valid transitions:
        - draft -> scheduled
        - scheduled -> ongoing
        - ongoing -> completed
        - completed -> published

        Args:
            exam_id: Exam UUID
            data: New status

        Returns:
            Updated Exam

        Raises:
            RecordNotFoundError: If exam not found
            ValueError: If invalid status transition
        """
        exam = await self.get_exam(exam_id)
        new_status = ExamStatus(data.status)

        # Validate status transitions
        valid_transitions = {
            ExamStatus.DRAFT: [ExamStatus.SCHEDULED],
            ExamStatus.SCHEDULED: [ExamStatus.ONGOING, ExamStatus.DRAFT],
            ExamStatus.ONGOING: [ExamStatus.COMPLETED],
            ExamStatus.COMPLETED: [ExamStatus.PUBLISHED],
            ExamStatus.PUBLISHED: [],
        }

        allowed = valid_transitions.get(exam.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{exam.status.value}' to '{new_status.value}'. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )

        exam.status = new_status

        # Lock marks when published
        if new_status == ExamStatus.PUBLISHED:
            exam.is_locked = True

        await self.db.commit()
        await self.db.refresh(exam)

        logger.info(f"Exam {exam.name} status updated to {new_status.value}")
        return await self.get_exam(exam.id)

    # ============================================================
    # Marks Management
    # ============================================================

    async def enter_marks(
        self,
        data: MarkEntryRequest,
        school_id: uuid.UUID,
        entered_by: uuid.UUID,
    ) -> List[Mark]:
        """
        Batch enter marks for students in a subject.

        Validates:
        - Exam is not locked
        - Marks don't exceed full marks
        - Calculates grade points (GPA system)

        Args:
            data: Mark entry request with subject and student entries
            school_id: School/tenant UUID
            entered_by: UUID of user entering marks

        Returns:
            List of created/updated Mark objects

        Raises:
            RecordNotFoundError: If exam subject not found
            ValueError: If exam is locked or marks exceed full marks
        """
        # Get exam subject
        result = await self.db.execute(
            select(ExamSubject)
            .where(ExamSubject.id == data.exam_subject_id)
            .options(selectinload(ExamSubject.exam))
        )
        exam_subject = result.scalar_one_or_none()

        if not exam_subject:
            raise RecordNotFoundError(
                f"Exam subject with ID {data.exam_subject_id} not found"
            )

        # Check if exam is locked
        if exam_subject.exam.is_locked:
            raise ValueError("Cannot enter marks - exam is locked")

        # Check exam status allows mark entry
        if exam_subject.exam.status == ExamStatus.PUBLISHED:
            raise ValueError("Cannot enter marks - results already published")

        full_marks = exam_subject.full_marks
        exam_id = exam_subject.exam_id
        grade_level = exam_subject.exam.grade
        student_ids = [entry.student_id for entry in data.entries]
        existing_result = await self.db.execute(
            select(Mark).where(
                Mark.exam_subject_id == data.exam_subject_id,
                Mark.student_id.in_(student_ids),
            )
        )
        existing_by_student = {
            mark.student_id: mark for mark in existing_result.scalars().all()
        }

        for entry in data.entries:
            # Validate marks don't exceed full marks
            if entry.marks_obtained > full_marks:
                raise ValueError(
                    f"Marks {entry.marks_obtained} exceed full marks {full_marks} "
                    f"for student {entry.student_id}"
                )

            if entry.marks_obtained < 0:
                raise ValueError(
                    f"Marks cannot be negative for student {entry.student_id}"
                )

            # Calculate grade point for GPA system (grades 1-10)
            grade_point = None
            if grade_level <= 10:
                grade_point = calculate_grade_point(entry.marks_obtained, full_marks)

            existing_mark = existing_by_student.get(entry.student_id)

            if existing_mark:
                # Update existing mark
                existing_mark.marks_obtained = entry.marks_obtained
                existing_mark.grade_point = grade_point
                existing_mark.remarks = entry.remarks
                existing_mark.entered_by = entered_by
            else:
                # Create new mark
                mark = Mark(
                    id=uuid.uuid4(),
                    school_id=school_id,
                    exam_id=exam_id,
                    exam_subject_id=data.exam_subject_id,
                    student_id=entry.student_id,
                    marks_obtained=entry.marks_obtained,
                    grade_point=grade_point,
                    remarks=entry.remarks,
                    entered_by=entered_by,
                )
                self.db.add(mark)

        await self.db.flush()
        marks_result = await self.db.execute(
            select(Mark).where(
                Mark.exam_subject_id == data.exam_subject_id,
                Mark.student_id.in_(student_ids),
            )
        )
        created_marks = list(marks_result.scalars().all())
        await self.db.commit()

        logger.info(
            f"Marks entered for exam_subject {data.exam_subject_id}: "
            f"{len(created_marks)} entries by user {entered_by}"
        )
        return created_marks

    # ============================================================
    # Result Calculation
    # ============================================================

    async def calculate_results(self, exam_id: uuid.UUID) -> List[Result]:
        """
        Calculate results for all students in an exam.

        Uses GPA system for grades 1-10 and percentage/division for 11-12.

        Algorithm:
        - Fetches all marks for the exam
        - Groups by student
        - For GPA (1-10): Averages grade points across subjects
        - For Percentage (11-12): Calculates total percentage and division
        - Determines pass/fail based on individual subject pass marks
        - Calculates rank by GPA or percentage

        Args:
            exam_id: Exam UUID

        Returns:
            List of calculated Result objects

        Raises:
            RecordNotFoundError: If exam not found
            ValueError: If no marks exist for the exam
        """
        exam = await self.get_exam(exam_id)

        if exam.is_locked:
            raise ValueError("Cannot recalculate - exam results are locked/published")

        # Get all exam subjects
        subjects_result = await self.db.execute(
            select(ExamSubject).where(ExamSubject.exam_id == exam_id)
        )
        exam_subjects = subjects_result.scalars().all()

        if not exam_subjects:
            raise ValueError("No subjects configured for this exam")

        subject_map = {s.id: s for s in exam_subjects}

        # Get all marks for this exam
        marks_result = await self.db.execute(
            select(Mark).where(Mark.exam_id == exam_id)
        )
        all_marks = marks_result.scalars().all()

        if not all_marks:
            raise ValueError("No marks entered for this exam yet")

        # Group marks by student
        student_marks = {}
        for mark in all_marks:
            if mark.student_id not in student_marks:
                student_marks[mark.student_id] = []
            student_marks[mark.student_id].append(mark)

        # Delete existing results for recalculation
        await self.db.execute(
            delete(Result).where(Result.exam_id == exam_id)
        )

        is_hs = exam.grade >= 11  # Higher Secondary uses percentage system
        results = []

        for student_id, marks in student_marks.items():
            total_obtained = Decimal("0")
            total_full = Decimal("0")
            grade_points = []
            all_passed = True

            for mark in marks:
                subject = subject_map.get(mark.exam_subject_id)
                if not subject:
                    continue

                total_obtained += mark.marks_obtained
                total_full += subject.full_marks

                # Check if student passed this subject
                if mark.marks_obtained < subject.pass_marks:
                    all_passed = False

                # Collect grade points for GPA calculation
                if mark.grade_point is not None:
                    grade_points.append(mark.grade_point)

            # Calculate percentage
            percentage = None
            if total_full > 0:
                percentage = (total_obtained / total_full * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

            # Determine GPA or Division
            gpa = None
            division = None

            if is_hs:
                # Percentage/Division system for grades 11-12
                if percentage is not None:
                    division = calculate_division(percentage)
            else:
                # GPA system for grades 1-10
                if grade_points:
                    gpa = (sum(grade_points) / len(grade_points)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

            # Determine result status
            if not marks:
                result_status = ResultStatus.ABSENT
            elif not all_passed:
                result_status = ResultStatus.FAIL
            else:
                result_status = ResultStatus.PASS

            # For HS, also check division for fail
            if is_hs and division == Division.FAIL:
                result_status = ResultStatus.FAIL

            result = Result(
                id=uuid.uuid4(),
                school_id=exam.school_id,
                exam_id=exam_id,
                student_id=student_id,
                total_marks=total_obtained,
                percentage=percentage,
                gpa=gpa,
                division=division,
                rank=None,  # Will be set after sorting
                status=result_status,
            )
            self.db.add(result)
            results.append(result)

        # Calculate ranks
        if is_hs:
            # Rank by percentage (descending)
            results.sort(key=lambda r: r.percentage or Decimal("0"), reverse=True)
        else:
            # Rank by GPA (descending)
            results.sort(key=lambda r: r.gpa or Decimal("0"), reverse=True)

        current_rank = 0
        prev_value = None
        for i, result in enumerate(results):
            # Only rank students who passed
            if result.status == ResultStatus.PASS:
                rank_value = result.gpa if not is_hs else result.percentage
                if rank_value != prev_value:
                    current_rank = i + 1
                result.rank = current_rank
                prev_value = rank_value
            else:
                result.rank = None

        await self.db.commit()

        # Refresh results
        for result in results:
            await self.db.refresh(result)

        logger.info(
            f"Results calculated for exam {exam.name}: "
            f"{len(results)} students processed"
        )
        return results

    # ============================================================
    # Report Card
    # ============================================================

    async def get_report_card(
        self,
        student_id: uuid.UUID,
        exam_id: uuid.UUID,
    ) -> dict:
        """
        Generate a complete report card for a student.

        Args:
            student_id: Student UUID
            exam_id: Exam UUID

        Returns:
            Dictionary with full report card data

        Raises:
            RecordNotFoundError: If exam or result not found
        """
        exam = await self.get_exam(exam_id)

        # Get student result
        result_query = await self.db.execute(
            select(Result).where(
                Result.exam_id == exam_id,
                Result.student_id == student_id,
            )
        )
        student_result = result_query.scalar_one_or_none()

        if not student_result:
            raise RecordNotFoundError(
                f"Result not found for student {student_id} in exam {exam_id}"
            )

        # Get all marks for this student in this exam
        marks_query = await self.db.execute(
            select(Mark)
            .where(
                Mark.exam_id == exam_id,
                Mark.student_id == student_id,
            )
            .options(selectinload(Mark.exam_subject))
        )
        student_marks = marks_query.scalars().all()

        # Build subject results
        subjects = []
        full_marks_total = Decimal("0")
        for mark in student_marks:
            exam_subject = mark.exam_subject
            full_marks_total += exam_subject.full_marks
            subjects.append({
                "subject_id": exam_subject.subject_id,
                "subject_name": None,  # To be resolved by API layer
                "full_marks": exam_subject.full_marks,
                "pass_marks": exam_subject.pass_marks,
                "marks_obtained": mark.marks_obtained,
                "grade_point": mark.grade_point,
                "remarks": mark.remarks,
            })

        is_hs = exam.grade >= 11

        return {
            "student_id": student_id,
            "student_name": None,  # To be resolved by API layer
            "exam_id": exam_id,
            "exam_name": exam.name,
            "exam_type": exam.exam_type.value,
            "academic_year_bs": exam.academic_year_bs,
            "grade": exam.grade,
            "subjects": subjects,
            "total_marks": student_result.total_marks,
            "full_marks_total": full_marks_total,
            "percentage": student_result.percentage,
            "gpa": student_result.gpa,
            "division": student_result.division.value if student_result.division else None,
            "rank": student_result.rank,
            "status": student_result.status.value,
            "grading_system": "percentage" if is_hs else "gpa",
        }

    # ============================================================
    # Publish Results
    # ============================================================

    async def publish_results(self, exam_id: uuid.UUID) -> Exam:
        """
        Publish exam results - locks the exam and transitions status.

        Prerequisites:
        - Exam must be in 'completed' status
        - Results must be calculated

        Args:
            exam_id: Exam UUID

        Returns:
            Updated Exam with published status

        Raises:
            RecordNotFoundError: If exam not found
            ValueError: If exam cannot be published
        """
        exam = await self.get_exam(exam_id)

        if exam.status != ExamStatus.COMPLETED:
            raise ValueError(
                f"Exam must be in 'completed' status to publish. "
                f"Current status: '{exam.status.value}'"
            )

        # Check if results exist
        result_count = await self.db.execute(
            select(func.count()).select_from(
                select(Result).where(Result.exam_id == exam_id).subquery()
            )
        )
        count = result_count.scalar()

        if not count or count == 0:
            raise ValueError(
                "Cannot publish - no results calculated. "
                "Run calculate_results first."
            )

        # Lock and publish
        exam.status = ExamStatus.PUBLISHED
        exam.is_locked = True

        await self.db.commit()
        await self.db.refresh(exam)

        logger.info(f"Exam results published: {exam.name} ({count} results)")
        return await self.get_exam(exam.id)

    # ============================================================
    # Results Retrieval
    # ============================================================

    async def get_results(
        self,
        exam_id: uuid.UUID,
        page: int = 1,
        limit: int = 50,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[Result], int]:
        """
        Get results for an exam with pagination.

        Args:
            exam_id: Exam UUID
            page: Page number (1-based)
            limit: Items per page
            status_filter: Filter by result status (pass/fail/absent)

        Returns:
            Tuple of (results list, total count)
        """
        # Verify exam exists
        await self.get_exam(exam_id)

        query = select(Result).where(Result.exam_id == exam_id)

        if status_filter:
            query = query.where(Result.status == ResultStatus(status_filter))

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate and order by rank
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(
            Result.rank.asc().nullslast(),
            Result.total_marks.desc(),
        )

        result = await self.db.execute(query)
        results = result.scalars().all()

        return results, total
