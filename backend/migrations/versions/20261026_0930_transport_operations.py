"""Scheduled transport, verified assignments, trips, upkeep and fee links."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "transport_operations"
down_revision = "hostel_operations"
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


def fk(name, target, nullable=False):
    return sa.Column(
        name,
        sa.UUID(),
        sa.ForeignKey(f"{target}.id", ondelete="RESTRICT"),
        nullable=nullable,
    )


def upgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM vehicles WHERE capacity NOT BETWEEN 1 AND 200)
        OR EXISTS (SELECT 1 FROM student_transport WHERE monthly_fee<0)
        OR EXISTS (SELECT 1 FROM student_transport a JOIN routes r ON r.id=a.route_id LEFT JOIN vehicles v ON v.id=a.vehicle_id LEFT JOIN route_stops s ON s.id=a.stop_id LEFT JOIN students st ON st.id=a.student_id
            WHERE a.school_id<>r.school_id OR (v.id IS NOT NULL AND v.school_id<>a.school_id) OR (s.id IS NOT NULL AND s.route_id<>r.id) OR (st.id IS NOT NULL AND st.school_id<>a.school_id))
        OR EXISTS (SELECT 1 FROM student_transport WHERE is_active GROUP BY school_id,student_id HAVING count(*)>1)
        OR EXISTS (SELECT 1 FROM route_stops WHERE stop_order<1 OR (latitude IS NULL)<>(longitude IS NULL) OR latitude NOT BETWEEN -90 AND 90 OR longitude NOT BETWEEN -180 AND 180)
        THEN RAISE EXCEPTION 'Reconcile legacy transport capacities, duplicate students, stop coordinates or school references before migration'; END IF;
    END $$""")
    op.execute(
        "UPDATE vehicles SET vehicle_number=translate(upper(btrim(vehicle_number)),'०१२३४५६७८९','0123456789')"
    )
    for name, length in [("helper_name", 200), ("helper_phone", 20), ("notes", 1000)]:
        op.add_column("vehicles", sa.Column(name, sa.String(length)))
    op.add_column(
        "vehicles",
        sa.Column(
            "condition", sa.String(20), nullable=False, server_default="available"
        ),
    )
    for name in [
        "insurance_expiry_ad",
        "tax_expiry_ad",
        "fitness_expiry_ad",
        "permit_expiry_ad",
        "driver_license_expiry_ad",
    ]:
        op.add_column("vehicles", sa.Column(name, sa.Date()))
    op.create_index(
        "uq_transport_vehicle_plate",
        "vehicles",
        [
            "school_id",
            sa.text("upper(regexp_replace(vehicle_number,'[[:space:]-]','','g'))"),
        ],
        unique=True,
    )
    op.create_check_constraint(
        "ck_transport_vehicle",
        "vehicles",
        "capacity BETWEEN 1 AND 200 AND condition IN ('available','maintenance')",
    )
    op.create_index(
        "uq_transport_route_name",
        "routes",
        ["school_id", sa.text("lower(btrim(name))")],
        unique=True,
    )
    for name in ["pickup_fee", "drop_fee", "both_fee"]:
        op.add_column(
            "routes",
            sa.Column(name, sa.Numeric(10, 2), nullable=False, server_default="0"),
        )
    op.create_check_constraint(
        "ck_transport_route_values",
        "routes",
        "pickup_fee >= 0 AND drop_fee >= 0 AND both_fee >= 0 AND (distance_km IS NULL OR distance_km >= 0) AND (estimated_time_minutes IS NULL OR estimated_time_minutes > 0)",
    )
    op.add_column("route_stops", sa.Column("school_id", sa.UUID()))
    op.execute(
        "UPDATE route_stops s SET school_id=r.school_id FROM routes r WHERE r.id=s.route_id"
    )
    op.alter_column("route_stops", "school_id", nullable=False)
    op.add_column(
        "route_stops",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("route_stops", sa.Column("notes", sa.String(1000)))
    for name in ["pickup_fee", "drop_fee", "both_fee"]:
        op.add_column("route_stops", sa.Column(name, sa.Numeric(10, 2)))
    op.create_index("ix_route_stops_school_id", "route_stops", ["school_id"])
    op.create_index(
        "uq_transport_stop_order",
        "route_stops",
        ["school_id", "route_id", "stop_order"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_transport_route_stops",
        "route_stops",
        ["school_id", "route_id", "is_active", "stop_order"],
    )
    op.create_check_constraint(
        "ck_transport_stop_values",
        "route_stops",
        "stop_order > 0 AND (latitude IS NULL OR latitude BETWEEN -90 AND 90) AND (longitude IS NULL OR longitude BETWEEN -180 AND 180) AND ((latitude IS NULL) = (longitude IS NULL)) AND (pickup_fee IS NULL OR pickup_fee >= 0) AND (drop_fee IS NULL OR drop_fee >= 0) AND (both_fee IS NULL OR both_fee >= 0)",
    )
    op.drop_constraint("route_stops_route_id_fkey", "route_stops", type_="foreignkey")
    op.create_foreign_key(
        "route_stops_route_id_fkey",
        "route_stops",
        "routes",
        ["route_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "transport_runs",
        *common(),
        sa.Column("name", sa.String(200), nullable=False),
        fk("route_id", "routes"),
        fk("vehicle_id", "vehicles"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("weekdays", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.CheckConstraint(
            "direction IN ('pickup','drop') AND end_time > start_time AND jsonb_typeof(weekdays)='array' AND jsonb_array_length(weekdays) BETWEEN 1 AND 7",
            name="ck_transport_run",
        ),
    )
    op.create_index(
        "uq_transport_run_name",
        "transport_runs",
        ["school_id", sa.text("lower(btrim(name))")],
        unique=True,
    )
    op.create_index(
        "ix_transport_vehicle_runs",
        "transport_runs",
        ["school_id", "vehicle_id", "is_active", "start_time"],
    )
    for col in [
        sa.Column("start_date_ad", sa.Date()),
        sa.Column("end_date_ad", sa.Date()),
        sa.Column(
            "needs_setup", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("notes", sa.String(1000)),
        sa.Column("end_reason", sa.String(1000)),
        sa.Column(
            "requires_handover", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("handover_contact", sa.String(200)),
        sa.Column("handover_phone", sa.String(20)),
        sa.Column("previous_assignment_id", sa.UUID()),
    ]:
        op.add_column("student_transport", col)
    for name, target in [
        ("pickup_run_id", "transport_runs"),
        ("drop_run_id", "transport_runs"),
        ("pickup_stop_id", "route_stops"),
        ("drop_stop_id", "route_stops"),
    ]:
        op.add_column("student_transport", sa.Column(name, sa.UUID()))
        op.create_foreign_key(
            f"fk_transport_{name}",
            "student_transport",
            target,
            [name],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_foreign_key(
        "fk_transport_previous_assignment",
        "student_transport",
        "student_transport",
        ["previous_assignment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""UPDATE student_transport a SET needs_setup=true,start_date_ad=(a.created_at AT TIME ZONE 'Asia/Kathmandu')::date,
        snapshot=jsonb_build_object('legacy',true,'student_name',coalesce((SELECT full_name_en FROM students st WHERE st.id=a.student_id AND st.school_id=a.school_id),'Legacy student'),
            'reference',(SELECT coalesce(admission_number,emis_student_id) FROM students st WHERE st.id=a.student_id AND st.school_id=a.school_id),'route_name',r.name,'stop_name',s.stop_name,'vehicle_number',v.vehicle_number),
        notes='Legacy assignment; reconcile scheduled runs and stops before dispatch. Start date is the original record creation date.'
        FROM routes r LEFT JOIN route_stops s ON false LEFT JOIN vehicles v ON false WHERE r.id=a.route_id""")
    op.execute(
        """UPDATE student_transport a SET snapshot=snapshot || jsonb_build_object('stop_name',s.stop_name) FROM route_stops s WHERE s.id=a.stop_id"""
    )
    op.execute(
        """UPDATE student_transport a SET snapshot=snapshot || jsonb_build_object('vehicle_number',v.vehicle_number) FROM vehicles v WHERE v.id=a.vehicle_id"""
    )
    op.create_index(
        "uq_transport_student_active",
        "student_transport",
        ["school_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    for kind in ["pickup", "drop"]:
        op.create_index(
            f"ix_transport_assignment_{kind}",
            "student_transport",
            ["school_id", f"{kind}_run_id", "is_active"],
        )
    op.create_check_constraint(
        "ck_transport_assignment",
        "student_transport",
        "monthly_fee >= 0 AND (end_date_ad IS NULL OR end_date_ad >= start_date_ad) AND (needs_setup OR (start_date_ad IS NOT NULL AND ((is_active AND end_date_ad IS NULL) OR (NOT is_active AND end_date_ad IS NOT NULL)) AND ((transport_type='PICKUP' AND pickup_run_id IS NOT NULL AND pickup_stop_id IS NOT NULL AND drop_run_id IS NULL AND drop_stop_id IS NULL) OR (transport_type='DROP' AND drop_run_id IS NOT NULL AND drop_stop_id IS NOT NULL AND pickup_run_id IS NULL AND pickup_stop_id IS NULL) OR (transport_type='BOTH' AND pickup_run_id IS NOT NULL AND pickup_stop_id IS NOT NULL AND drop_run_id IS NOT NULL AND drop_stop_id IS NOT NULL))))",
    )
    op.create_table(
        "transport_trips",
        *common(),
        fk("run_id", "transport_runs"),
        fk("vehicle_id", "vehicles"),
        sa.Column("date_ad", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("sweep_confirmed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','cancelled') AND (ended_at IS NULL OR ended_at >= started_at)",
            name="ck_transport_trip",
        ),
    )
    op.create_index(
        "uq_transport_run_trip_day",
        "transport_trips",
        ["school_id", "run_id", "date_ad"],
        unique=True,
        postgresql_where=sa.text("status<>'cancelled'"),
    )
    op.create_index(
        "uq_transport_vehicle_in_progress",
        "transport_trips",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status='in_progress'"),
    )
    op.create_index(
        "ix_transport_trip_register",
        "transport_trips",
        ["school_id", "date_ad", "status"],
    )
    op.create_table(
        "transport_passengers",
        *common(),
        fk("trip_id", "transport_trips"),
        fk("assignment_id", "student_transport"),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("stop_name", sa.String(200), nullable=False),
        sa.Column("stop_order", sa.Integer(), nullable=False),
        sa.Column("requires_handover", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("boarded_at", sa.DateTime(timezone=True)),
        sa.Column("alighted_at", sa.DateTime(timezone=True)),
        sa.Column("received_by", sa.String(200)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','boarded','alighted','absent','cancelled') AND version > 0",
            name="ck_transport_passenger",
        ),
    )
    op.create_index(
        "uq_transport_trip_student",
        "transport_passengers",
        ["trip_id", "student_id"],
        unique=True,
    )
    op.create_index(
        "ix_transport_passenger_assignment",
        "transport_passengers",
        ["school_id", "assignment_id", "trip_id"],
    )
    op.create_table(
        "transport_maintenance",
        *common(),
        fk("vehicle_id", "vehicles"),
        sa.Column("service_date_ad", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("odometer_km", sa.Integer()),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("next_due_ad", sa.Date()),
        sa.Column("vendor", sa.String(200)),
        sa.Column("notes", sa.String(1000), nullable=False),
        sa.CheckConstraint(
            "cost >= 0 AND (odometer_km IS NULL OR odometer_km >= 0) AND (next_due_ad IS NULL OR next_due_ad >= service_date_ad)",
            name="ck_transport_maintenance",
        ),
    )
    op.create_index(
        "ix_transport_maintenance_due",
        "transport_maintenance",
        ["school_id", "vehicle_id", "next_due_ad"],
    )
    op.create_table(
        "transport_positions",
        *common(),
        fk("vehicle_id", "vehicles"),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("accuracy_m", sa.Numeric(10, 2)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 AND (accuracy_m IS NULL OR accuracy_m >= 0) AND source IN ('manual','device')",
            name="ck_transport_position",
        ),
    )
    op.create_index(
        "ix_transport_vehicle_position",
        "transport_positions",
        ["school_id", "vehicle_id", "recorded_at"],
    )
    op.create_table(
        "transport_charges",
        *common(),
        fk("assignment_id", "student_transport"),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("month_bs", sa.String(7), nullable=False),
        fk("ledger_id", "fee_ledger"),
    )
    op.create_index(
        "uq_transport_student_month",
        "transport_charges",
        ["school_id", "student_id", "month_bs"],
        unique=True,
    )
    op.create_table(
        "transport_events",
        *common(),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("actor_name", sa.String(200)),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("before_values", JSONB(), nullable=False),
    )
    op.create_index(
        "uq_transport_request",
        "transport_events",
        ["school_id", "request_id"],
        unique=True,
    )
    op.create_index(
        "ix_transport_history", "transport_events", ["school_id", "created_at"]
    )
    for table in [
        "transport_runs",
        "transport_trips",
        "transport_passengers",
        "transport_maintenance",
        "transport_positions",
        "transport_charges",
        "transport_events",
    ]:
        op.create_index(f"ix_{table}_id", table, ["id"], unique=True)
        op.create_index(f"ix_{table}_school_id", table, ["school_id"])


def downgrade():
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM transport_events) THEN RAISE EXCEPTION 'Cannot discard recorded transport operational/billing history'; END IF; END $$"""
    )
    for table in [
        "transport_events",
        "transport_charges",
        "transport_positions",
        "transport_maintenance",
        "transport_passengers",
        "transport_trips",
    ]:
        op.drop_table(table)
    for name in [
        "uq_transport_student_active",
        "ix_transport_assignment_pickup",
        "ix_transport_assignment_drop",
    ]:
        op.drop_index(name, table_name="student_transport")
    op.drop_constraint("ck_transport_assignment", "student_transport", type_="check")
    for name in ["pickup_run_id", "drop_run_id", "pickup_stop_id", "drop_stop_id"]:
        op.drop_constraint(
            f"fk_transport_{name}", "student_transport", type_="foreignkey"
        )
    op.drop_constraint(
        "fk_transport_previous_assignment", "student_transport", type_="foreignkey"
    )
    for name in [
        "pickup_run_id",
        "drop_run_id",
        "pickup_stop_id",
        "drop_stop_id",
        "start_date_ad",
        "end_date_ad",
        "needs_setup",
        "snapshot",
        "notes",
        "end_reason",
        "requires_handover",
        "handover_contact",
        "handover_phone",
        "previous_assignment_id",
    ]:
        op.drop_column("student_transport", name)
    op.drop_table("transport_runs")
    for name in [
        "uq_transport_stop_order",
        "ix_transport_route_stops",
        "ix_route_stops_school_id",
    ]:
        op.drop_index(name, table_name="route_stops")
    op.drop_constraint("ck_transport_stop_values", "route_stops", type_="check")
    op.drop_constraint("route_stops_route_id_fkey", "route_stops", type_="foreignkey")
    op.create_foreign_key(
        "route_stops_route_id_fkey",
        "route_stops",
        "routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for name in [
        "school_id",
        "is_active",
        "notes",
        "pickup_fee",
        "drop_fee",
        "both_fee",
    ]:
        op.drop_column("route_stops", name)
    op.drop_constraint("ck_transport_route_values", "routes", type_="check")
    op.drop_index("uq_transport_route_name", table_name="routes")
    for name in ["pickup_fee", "drop_fee", "both_fee"]:
        op.drop_column("routes", name)
    op.drop_constraint("ck_transport_vehicle", "vehicles", type_="check")
    op.drop_index("uq_transport_vehicle_plate", table_name="vehicles")
    for name in [
        "helper_name",
        "helper_phone",
        "notes",
        "condition",
        "insurance_expiry_ad",
        "tax_expiry_ad",
        "fitness_expiry_ad",
        "permit_expiry_ad",
        "driver_license_expiry_ad",
    ]:
        op.drop_column("vehicles", name)
