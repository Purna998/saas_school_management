"""Physical beds, residential operations, registers and fee links."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "hostel_operations"
down_revision = "library_circulation"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def stay_fk():
    return sa.Column(
        "allocation_id",
        sa.UUID(),
        sa.ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )


def upgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM hostel_rooms r JOIN hostels h ON h.id=r.hostel_id WHERE r.school_id<>h.school_id
            OR r.capacity IS NULL OR r.occupied IS NULL OR r.capacity<0 OR r.occupied<0 OR r.occupied>r.capacity OR r.monthly_fee IS NULL OR r.monthly_fee<0
            OR r.occupied<>(SELECT count(*) FROM room_allocations a WHERE a.room_id=r.id AND a.status='ACTIVE'))
        OR EXISTS (SELECT 1 FROM hostel_rooms r JOIN hostels h ON h.id=r.hostel_id WHERE r.occupied>0 AND (r.is_active IS NOT TRUE OR h.is_active IS NOT TRUE))
        OR EXISTS (SELECT 1 FROM room_allocations a JOIN hostel_rooms r ON r.id=a.room_id WHERE a.school_id<>r.school_id OR a.status IS NULL OR a.allocated_date_ad IS NULL
            OR (a.vacated_date_ad IS NOT NULL AND a.vacated_date_ad<a.allocated_date_ad)
            OR (a.status='ACTIVE' AND a.vacated_date_ad IS NOT NULL) OR (a.status='VACATED' AND a.vacated_date_ad IS NULL))
        OR EXISTS (SELECT 1 FROM room_allocations WHERE status='ACTIVE' GROUP BY school_id,student_id HAVING count(*)>1)
        OR EXISTS (SELECT 1 FROM room_allocations a JOIN students s ON s.id=a.student_id WHERE a.school_id<>s.school_id)
        THEN RAISE EXCEPTION 'Reconcile legacy hostel occupancy, allocation dates or school references before migration'; END IF;
    END $$""")
    for name, length in [("address", 300), ("notes", 1000)]:
        op.add_column("hostels", sa.Column(name, sa.String(length)))
    op.add_column("hostel_rooms", sa.Column("notes", sa.String(1000)))
    op.create_index(
        "uq_hostel_name",
        "hostels",
        ["school_id", sa.text("lower(btrim(name))")],
        unique=True,
    )
    op.create_index(
        "uq_hostel_room_number",
        "hostel_rooms",
        ["school_id", "hostel_id", sa.text("upper(btrim(room_number))")],
        unique=True,
    )
    op.create_check_constraint(
        "ck_hostel_room_values",
        "hostel_rooms",
        "capacity >= 0 AND occupied >= 0 AND occupied <= capacity AND monthly_fee >= 0",
    )
    op.create_table(
        "hostel_beds",
        *common(),
        sa.Column(
            "room_id",
            sa.UUID(),
            sa.ForeignKey("hostel_rooms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("label", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.CheckConstraint(
            "status IN ('active','maintenance','retired')", name="ck_hostel_bed_status"
        ),
    )
    op.create_index(
        "uq_hostel_bed_label",
        "hostel_beds",
        ["school_id", "room_id", "label"],
        unique=True,
    )
    op.create_index(
        "ix_hostel_bed_inventory", "hostel_beds", ["school_id", "room_id", "status"]
    )
    for col in [
        sa.Column("bed_id", sa.UUID()),
        sa.Column("student_name", sa.String(200)),
        sa.Column("student_reference", sa.String(100)),
        sa.Column("hostel_name", sa.String(200)),
        sa.Column("room_number", sa.String(20)),
        sa.Column("bed_label", sa.String(30)),
        sa.Column("monthly_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(1000)),
        sa.Column("checkout_reason", sa.String(1000)),
        sa.Column("previous_allocation_id", sa.UUID()),
    ]:
        op.add_column("room_allocations", col)
    op.execute("""INSERT INTO hostel_beds (id,school_id,room_id,label,status)
        SELECT gen_random_uuid(),school_id,id,'B-'||lpad(n::text,4,'0'),'active' FROM hostel_rooms CROSS JOIN LATERAL generate_series(1,capacity) n""")
    op.execute("""WITH stays AS (SELECT id,room_id,row_number() OVER (PARTITION BY room_id ORDER BY created_at,id) n FROM room_allocations WHERE status='ACTIVE'),
        beds AS (SELECT id,room_id,label,row_number() OVER (PARTITION BY room_id ORDER BY label) n FROM hostel_beds)
        UPDATE room_allocations a SET bed_id=b.id,bed_label=b.label FROM stays s JOIN beds b ON b.room_id=s.room_id AND b.n=s.n WHERE a.id=s.id""")
    op.execute("""UPDATE room_allocations a SET student_name=coalesce((SELECT full_name_en FROM students s WHERE s.id=a.student_id AND s.school_id=a.school_id),'Legacy resident'),
        student_reference=(SELECT coalesce(admission_number,emis_student_id) FROM students s WHERE s.id=a.student_id AND s.school_id=a.school_id),
        hostel_name=h.name,room_number=r.room_number,monthly_fee=r.monthly_fee,notes='Legacy stay; room and rate snapshots assigned during migration'
        FROM hostel_rooms r JOIN hostels h ON h.id=r.hostel_id WHERE a.room_id=r.id""")
    for name in ["student_name", "hostel_name", "room_number"]:
        op.alter_column("room_allocations", name, nullable=False)
    op.create_foreign_key(
        "fk_hostel_allocation_bed",
        "room_allocations",
        "hostel_beds",
        ["bed_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_hostel_previous_stay",
        "room_allocations",
        "room_allocations",
        ["previous_allocation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for table, col, target in [
        ("room_allocations", "room_id", "hostel_rooms"),
        ("hostel_rooms", "hostel_id", "hostels"),
    ]:
        op.drop_constraint(f"{table}_{col}_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{col}_fkey", table, target, [col], ["id"], ondelete="RESTRICT"
        )
    op.create_index(
        "uq_hostel_student_active",
        "room_allocations",
        ["school_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status='ACTIVE'"),
    )
    op.create_index(
        "uq_hostel_bed_active",
        "room_allocations",
        ["bed_id"],
        unique=True,
        postgresql_where=sa.text("status='ACTIVE'"),
    )
    op.create_index(
        "ix_hostel_resident_register",
        "room_allocations",
        ["school_id", "status", "room_id", "allocated_date_ad"],
    )
    op.create_index(
        "ix_hostel_student_stay_dates",
        "room_allocations",
        ["school_id", "student_id", "allocated_date_ad", "created_at", "id"],
    )
    for name in ["status", "allocated_date_ad"]:
        op.alter_column("room_allocations", name, nullable=False)
    op.create_check_constraint(
        "ck_hostel_allocation_values",
        "room_allocations",
        "monthly_fee >= 0 AND (vacated_date_ad IS NULL OR vacated_date_ad >= allocated_date_ad) AND ((status='ACTIVE' AND bed_id IS NOT NULL AND vacated_date_ad IS NULL) OR (status='VACATED' AND vacated_date_ad IS NOT NULL))",
    )
    op.create_table(
        "hostel_leaves",
        *common(),
        stay_fk(),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_return_ad", sa.Date(), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("responsible_person", sa.String(200), nullable=False),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("return_notes", sa.String(1000)),
        sa.CheckConstraint(
            "returned_at IS NULL OR returned_at >= departed_at",
            name="ck_hostel_leave_times",
        ),
    )
    op.create_index(
        "uq_hostel_open_leave",
        "hostel_leaves",
        ["allocation_id"],
        unique=True,
        postgresql_where=sa.text("returned_at IS NULL"),
    )
    op.create_index(
        "ix_hostel_leave_due",
        "hostel_leaves",
        ["school_id", "expected_return_ad"],
        postgresql_where=sa.text("returned_at IS NULL"),
    )
    op.create_table(
        "hostel_visits",
        *common(),
        stay_fk(),
        sa.Column("visitor_name", sa.String(200), nullable=False),
        sa.Column("relation", sa.String(50), nullable=False),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("purpose", sa.String(500), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("departed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "departed_at IS NULL OR departed_at >= arrived_at",
            name="ck_hostel_visit_times",
        ),
    )
    op.create_index(
        "ix_hostel_visit_register",
        "hostel_visits",
        ["school_id", "allocation_id", "arrived_at"],
    )
    op.create_table(
        "hostel_register",
        *common(),
        stay_fk(),
        sa.Column("date_ad", sa.Date(), nullable=False),
        sa.Column("session", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_by", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(session IN ('morning','evening') AND status IN ('present','absent','on_leave','excused')) OR (session IN ('breakfast','lunch','snacks','dinner') AND status IN ('taken','skipped'))",
            name="ck_hostel_register_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_hostel_register_version"),
    )
    op.create_index(
        "uq_hostel_register_entry",
        "hostel_register",
        ["school_id", "allocation_id", "date_ad", "session"],
        unique=True,
    )
    op.create_index(
        "ix_hostel_register_date",
        "hostel_register",
        ["school_id", "date_ad", "session"],
    )
    op.create_table(
        "hostel_charges",
        *common(),
        stay_fk(),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("month_bs", sa.String(7), nullable=False),
        sa.Column(
            "ledger_id",
            sa.UUID(),
            sa.ForeignKey("fee_ledger.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_hostel_charge_month",
        "hostel_charges",
        ["school_id", "student_id", "month_bs"],
        unique=True,
    )
    op.create_table(
        "hostel_events",
        *common(),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column(
            "allocation_id",
            sa.UUID(),
            sa.ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        ),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("actor_name", sa.String(200)),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("before_values", JSONB(), nullable=False),
    )
    op.create_index(
        "uq_hostel_request", "hostel_events", ["school_id", "request_id"], unique=True
    )
    op.create_index("ix_hostel_history", "hostel_events", ["school_id", "created_at"])
    op.create_index(
        "ix_hostel_stay_history",
        "hostel_events",
        ["school_id", "allocation_id", "created_at"],
    )
    for table in [
        "hostel_beds",
        "hostel_leaves",
        "hostel_visits",
        "hostel_register",
        "hostel_charges",
        "hostel_events",
    ]:
        op.create_index(f"ix_{table}_id", table, ["id"], unique=True)
        op.create_index(f"ix_{table}_school_id", table, ["school_id"])
    op.execute("""UPDATE hostels h SET total_rooms=(SELECT count(*) FROM hostel_rooms r WHERE r.hostel_id=h.id AND r.is_active),
        capacity=coalesce((SELECT sum(capacity) FROM hostel_rooms r WHERE r.hostel_id=h.id AND r.is_active),0)""")


def downgrade():
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM hostel_events) THEN RAISE EXCEPTION 'Cannot discard hostel operational and billing history'; END IF; END $$"""
    )
    for table in [
        "hostel_events",
        "hostel_charges",
        "hostel_register",
        "hostel_visits",
        "hostel_leaves",
    ]:
        op.drop_table(table)
    for name in [
        "uq_hostel_student_active",
        "uq_hostel_bed_active",
        "ix_hostel_resident_register",
        "ix_hostel_student_stay_dates",
    ]:
        op.drop_index(name, table_name="room_allocations")
    for name in [
        "ck_hostel_allocation_values",
        "fk_hostel_allocation_bed",
        "fk_hostel_previous_stay",
    ]:
        op.drop_constraint(name, "room_allocations")
    for name in ["status", "allocated_date_ad"]:
        op.alter_column("room_allocations", name, nullable=True)
    for table, col, target in [
        ("room_allocations", "room_id", "hostel_rooms"),
        ("hostel_rooms", "hostel_id", "hostels"),
    ]:
        op.drop_constraint(f"{table}_{col}_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{col}_fkey", table, target, [col], ["id"], ondelete="CASCADE"
        )
    for col in [
        "bed_id",
        "student_name",
        "student_reference",
        "hostel_name",
        "room_number",
        "bed_label",
        "monthly_fee",
        "notes",
        "checkout_reason",
        "previous_allocation_id",
    ]:
        op.drop_column("room_allocations", col)
    op.drop_table("hostel_beds")
    op.drop_constraint("ck_hostel_room_values", "hostel_rooms", type_="check")
    op.drop_index("uq_hostel_room_number", table_name="hostel_rooms")
    op.drop_index("uq_hostel_name", table_name="hostels")
    op.drop_column("hostel_rooms", "notes")
    op.drop_column("hostels", "notes")
    op.drop_column("hostels", "address")
