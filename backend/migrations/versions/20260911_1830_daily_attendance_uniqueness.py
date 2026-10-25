"""Keep daily attendance saves idempotent.

Revision ID: daily_attendance_unique
Revises: subject_stream_groups
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "daily_attendance_unique"
down_revision: Union[str, None] = "subject_stream_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve the most recently updated row if an older installation already
    # accumulated duplicate daily records under PostgreSQL NULL semantics.
    op.execute(
        """
        DELETE FROM attendances older
        USING attendances newer
        WHERE older.school_id = newer.school_id
          AND older.student_id = newer.student_id
          AND older.date_ad = newer.date_ad
          AND older.period_number IS NULL
          AND newer.period_number IS NULL
          AND (older.updated_at, older.id) < (newer.updated_at, newer.id)
        """
    )
    op.create_index(
        "uq_attendance_daily_student_date",
        "attendances",
        ["school_id", "student_id", "date_ad"],
        unique=True,
        postgresql_where=sa.text("period_number IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_daily_student_date", table_name="attendances")
