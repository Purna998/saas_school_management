"""Phone-first tracking and explicitly verified family access."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "transport_live"
down_revision = "transport_operations"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
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
    ]


def fk(name, table):
    return sa.Column(
        name,
        sa.UUID(),
        sa.ForeignKey(f"{table}.id", ondelete="RESTRICT"),
        nullable=False,
    )


def upgrade():
    op.add_column(
        "transport_trips",
        sa.Column(
            "tracking_progress",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "transport_passengers",
        sa.Column(
            "stop_snapshot",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_table(
        "transport_family_access",
        *common(),
        fk("student_id", "students"),
        fk("parent_id", "users"),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_transport_family_active",
        "transport_family_access",
        ["school_id", "student_id", "parent_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_transport_family_viewer",
        "transport_family_access",
        ["school_id", "parent_id", "revoked_at"],
    )
    op.create_table(
        "transport_phone_sessions",
        *common(),
        fk("trip_id", "transport_trips"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_transport_phone_token",
        "transport_phone_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "uq_transport_trip_phone_active",
        "transport_phone_sessions",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "transport_live_positions",
        *common(),
        fk("vehicle_id", "vehicles"),
        fk("trip_id", "transport_trips"),
        fk("session_id", "transport_phone_sessions"),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("accuracy_m", sa.Numeric(10, 2), nullable=False),
        sa.Column("speed_mps", sa.Numeric(6, 2)),
        sa.Column("heading", sa.Numeric(6, 2)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 AND accuracy_m BETWEEN 0 AND 10000 AND (speed_mps IS NULL OR speed_mps BETWEEN 0 AND 60) AND (heading IS NULL OR heading BETWEEN 0 AND 360)",
            name="ck_transport_live_fix",
        ),
    )
    op.create_index(
        "uq_transport_live_vehicle",
        "transport_live_positions",
        ["vehicle_id"],
        unique=True,
    )
    op.create_index(
        "ix_transport_live_trip", "transport_live_positions", ["school_id", "trip_id"]
    )
    op.create_index(
        "ix_transport_family_passenger",
        "transport_passengers",
        ["school_id", "student_id", "trip_id"],
    )
    op.create_index(
        "ix_transport_open_tracking",
        "transport_trips",
        ["school_id", "started_at"],
        postgresql_where=sa.text("status='in_progress'"),
    )
    # No guessed guardian links, historic stop coordinates or sender credentials.
    op.execute("""INSERT INTO permissions (id,code,name_en,resource,action,is_active,created_at,updated_at)
        VALUES (gen_random_uuid(),'transport:track','View live school transport','transport','track',true,now(),now()) ON CONFLICT (code) DO NOTHING""")
    op.execute("""INSERT INTO role_permissions (id,role_id,permission_id)
        SELECT gen_random_uuid(),r.id,p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code IN ('school_admin','principal','vice_principal','teacher','receptionist') AND p.code='transport:track'
        AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)""")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM transport_family_access) OR EXISTS (SELECT 1 FROM transport_phone_sessions)
        THEN RAISE EXCEPTION 'Refusing to discard transport sharing and family access history'; END IF; END $$""")
    op.drop_index("ix_transport_open_tracking", table_name="transport_trips")
    op.drop_index("ix_transport_family_passenger", table_name="transport_passengers")
    for table in (
        "transport_live_positions",
        "transport_phone_sessions",
        "transport_family_access",
    ):
        op.drop_table(table)
    op.drop_column("transport_passengers", "stop_snapshot")
    op.drop_column("transport_trips", "tracking_progress")
