"""Add tenant, student, and academic models

Revision ID: 002_tenant_student_academic
Revises: 001_initial_auth_models
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_tenant_student_academic'
down_revision = '001_initial_auth_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Tenants ---
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name_en', sa.String(255), nullable=False),
        sa.Column('name_np', sa.String(255), nullable=True),
        sa.Column('emis_code', sa.String(20), unique=True, nullable=True, index=True),
        sa.Column('registration_number', sa.String(50), nullable=True),
        sa.Column('school_type', sa.String(20), nullable=False, server_default='institutional'),
        sa.Column('school_level', sa.String(20), nullable=False, server_default='secondary'),
        sa.Column('hs_enabled', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('hs_enabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('province', sa.String(20), nullable=True),
        sa.Column('district', sa.String(100), nullable=True),
        sa.Column('municipality', sa.String(100), nullable=True),
        sa.Column('ward_no', sa.Integer(), nullable=True),
        sa.Column('tole', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='trial', index=True),
        sa.Column('subscription_plan', sa.String(20), nullable=False, server_default='free'),
        sa.Column('subscription_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('subscription_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('academic_year_bs', sa.String(10), nullable=True),
        sa.Column('academic_year_start_month', sa.Integer(), server_default='1'),
        sa.Column('max_students', sa.Integer(), server_default='500'),
        sa.Column('max_staff', sa.Integer(), server_default='50'),
        sa.Column('max_storage_gb', sa.Integer(), server_default='5'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), server_default='#1E40AF'),
        sa.Column('settings_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('onboarded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Students ---
    op.create_table(
        'students',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('emis_student_id', sa.String(30), unique=True, nullable=True, index=True),
        sa.Column('admission_number', sa.String(30), nullable=True, index=True),
        sa.Column('roll_number', sa.Integer(), nullable=True),
        sa.Column('full_name_en', sa.String(200), nullable=False),
        sa.Column('full_name_np', sa.String(200), nullable=True),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('date_of_birth_ad', sa.Date(), nullable=False),
        sa.Column('date_of_birth_bs', sa.String(12), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('address_permanent', sa.Text(), nullable=True),
        sa.Column('address_temporary', sa.Text(), nullable=True),
        sa.Column('current_grade', sa.Integer(), nullable=True),
        sa.Column('current_section', sa.String(10), nullable=True),
        sa.Column('current_faculty', sa.String(50), nullable=True),
        sa.Column('admission_date_ad', sa.Date(), nullable=True),
        sa.Column('admission_date_bs', sa.String(12), nullable=True),
        sa.Column('caste_ethnicity', sa.String(30), nullable=True),
        sa.Column('religion', sa.String(50), nullable=True),
        sa.Column('mother_tongue', sa.String(50), nullable=True),
        sa.Column('nationality', sa.String(50), server_default='Nepali'),
        sa.Column('disability_type', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('previous_school_name', sa.String(255), nullable=True),
        sa.Column('previous_school_emis', sa.String(20), nullable=True),
        sa.Column('transfer_certificate_number', sa.String(50), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', index=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Student Guardians ---
    op.create_table(
        'student_guardians',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relation', sa.String(20), nullable=False),
        sa.Column('full_name_en', sa.String(200), nullable=False),
        sa.Column('full_name_np', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('occupation', sa.String(100), nullable=True),
        sa.Column('is_primary_contact', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Student Enrollments ---
    op.create_table(
        'student_enrollments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('academic_year_bs', sa.String(10), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(10), nullable=True),
        sa.Column('faculty', sa.String(50), nullable=True),
        sa.Column('roll_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='enrolled'),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('promoted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Grades ---
    op.create_table(
        'grades',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('grade_number', sa.Integer(), nullable=False),
        sa.Column('name_en', sa.String(50), nullable=False),
        sa.Column('name_np', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_hs', sa.Boolean(), server_default='false'),
        sa.Column('academic_year_bs', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Sections ---
    op.create_table(
        'sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grades.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(10), nullable=False),
        sa.Column('capacity', sa.Integer(), server_default='40'),
        sa.Column('class_teacher_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- HS Faculties ---
    op.create_table(
        'hs_faculties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name_en', sa.String(100), nullable=False),
        sa.Column('name_np', sa.String(100), nullable=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('max_students', sa.Integer(), server_default='60'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- HS Streams ---
    op.create_table(
        'hs_streams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('faculty_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hs_faculties.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name_en', sa.String(100), nullable=False),
        sa.Column('name_np', sa.String(100), nullable=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Subjects ---
    op.create_table(
        'subjects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grades.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('name_en', sa.String(100), nullable=False),
        sa.Column('name_np', sa.String(100), nullable=True),
        sa.Column('subject_type', sa.String(20), nullable=False, server_default='compulsory'),
        sa.Column('full_marks', sa.Integer(), server_default='100'),
        sa.Column('pass_marks', sa.Integer(), server_default='40'),
        sa.Column('credit_hours', sa.Integer(), server_default='4'),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('faculty_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hs_faculties.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Timetable Entries ---
    op.create_table(
        'timetable_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('grade_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('grades.id'), nullable=False, index=True),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sections.id'), nullable=False),
        sa.Column('subject_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('day_of_week', sa.String(10), nullable=False),
        sa.Column('period_number', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('room', sa.String(20), nullable=True),
        sa.Column('academic_year_bs', sa.String(10), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('timetable_entries')
    op.drop_table('subjects')
    op.drop_table('hs_streams')
    op.drop_table('hs_faculties')
    op.drop_table('sections')
    op.drop_table('grades')
    op.drop_table('student_enrollments')
    op.drop_table('student_guardians')
    op.drop_table('students')
    op.drop_table('tenants')
