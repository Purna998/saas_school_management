"""Replace placeholder reports with immutable school data snapshots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "report_workspace"
down_revision = "transport_live"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE reports ALTER COLUMN report_type TYPE varchar(40) USING lower(report_type::text)"
    )
    for column in [
        sa.Column("request_id", sa.UUID()),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "columns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "summary", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "school_snapshot",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "notes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("generated_by_name", sa.String(200)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("archive_reason", sa.String(1000)),
    ]:
        op.add_column("reports", column)
    op.execute(
        "UPDATE reports SET status='EXPIRED',file_url=NULL,error_message='Legacy placeholder output is unverified. Generate a new report from school records.'"
    )
    op.alter_column("reports", "snapshot_version", server_default="2")
    op.create_index(
        "uq_report_request", "reports", ["school_id", "request_id"], unique=True
    )
    op.create_index(
        "ix_report_history", "reports", ["school_id", "report_type", "created_at"]
    )
    op.create_table(
        "report_rows",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column(
            "report_id",
            sa.UUID(),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("values", JSONB, nullable=False),
    )
    op.create_index(
        "uq_report_row", "report_rows", ["report_id", "ordinal"], unique=True
    )
    op.create_table(
        "report_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column(
            "report_id",
            sa.UUID(),
            sa.ForeignKey("reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("actor_name", sa.String(200)),
        sa.Column("notes", sa.String(1000)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_report_event_request",
        "report_events",
        ["school_id", "request_id"],
        unique=True,
    )
    op.create_index(
        "ix_report_activity", "report_events", ["school_id", "report_id", "created_at"]
    )
    op.execute("""INSERT INTO role_permissions (id,role_id,permission_id)
        SELECT gen_random_uuid(),r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code IN ('accountant','vice_principal') AND p.code IN ('report:read','report:export')
        AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)""")


def downgrade():
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM reports WHERE snapshot_version=2)
        OR EXISTS (SELECT 1 FROM report_events) OR EXISTS (SELECT 1 FROM report_rows)
        THEN RAISE EXCEPTION 'Refusing to discard school report snapshots or activity'; END IF; END $$"""
    )
    op.drop_table("report_events")
    op.drop_table("report_rows")
    op.drop_index("ix_report_history", table_name="reports")
    op.drop_index("uq_report_request", table_name="reports")
    for name in [
        "request_id",
        "request_hash",
        "snapshot_version",
        "row_count",
        "columns",
        "summary",
        "school_snapshot",
        "notes",
        "content_hash",
        "generated_by_name",
        "archived_at",
        "archive_reason",
    ]:
        op.drop_column("reports", name)
    op.execute(
        "ALTER TABLE reports ALTER COLUMN report_type TYPE reporttype USING upper(report_type)::reporttype"
    )
