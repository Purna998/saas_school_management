"""Index tenant directories, class rosters and BS monthly attendance reports.

Revision ID: class_query_indexes
Revises: exam_mark_absence
"""

from alembic import op
import sqlalchemy as sa


revision = "class_query_indexes"
down_revision = "exam_mark_absence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Concurrent builds allow existing school reads/writes during deployment.
    # PostgreSQL requires these operations outside a transaction block.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_students_live_directory", "students",
            ["school_id", "current_grade", "roll_number", "full_name_en", "id"],
            postgresql_where=sa.text("deleted_at IS NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_students_live_class_roster", "students",
            ["school_id", "current_grade", "current_section", "status",
             "roll_number", "full_name_en", "id"],
            postgresql_where=sa.text("deleted_at IS NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_attendance_class_bs_month", "attendances",
            ["school_id", "grade", "section", "date_bs"],
            postgresql_include=["date_ad", "status"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_attendance_class_bs_month", table_name="attendances", postgresql_concurrently=True)
        op.drop_index("ix_students_live_class_roster", table_name="students", postgresql_concurrently=True)
        op.drop_index("ix_students_live_directory", table_name="students", postgresql_concurrently=True)
