"""Add flexible Grade 11-12 subject stream assignments.

Revision ID: subject_stream_groups
Revises: aeb7255317fb
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "subject_stream_groups"
down_revision: Union[str, None] = "aeb7255317fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subjects", sa.Column("optional_group", sa.String(length=30), nullable=True))
    op.add_column("sections", sa.Column("stream_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_sections_stream_id", "sections", "hs_streams", ["stream_id"], ["id"])
    op.create_table(
        "subject_streams",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stream_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["hs_streams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subject_id", "stream_id"),
    )


def downgrade() -> None:
    op.drop_table("subject_streams")
    op.drop_constraint("fk_sections_stream_id", "sections", type_="foreignkey")
    op.drop_column("sections", "stream_id")
    op.drop_column("subjects", "optional_group")
