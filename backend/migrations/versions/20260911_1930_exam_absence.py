"""Support absent students in exam mark sheets.

Revision ID: exam_mark_absence
Revises: daily_attendance_unique
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "exam_mark_absence"
down_revision: Union[str, None] = "daily_attendance_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marks",
        sa.Column("is_absent", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("marks", "is_absent")
