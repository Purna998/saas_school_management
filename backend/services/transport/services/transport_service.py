"""Transactional school transport with scheduled seats and frozen trip rosters."""

import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import func, or_, select, text, union_all, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from services.transport.models.transport import (
    Vehicle,
    Route,
    RouteStop,
    StudentTransport,
    TransportRun,
    TransportTrip,
    TransportPassenger,
    TransportMaintenance,
    VehiclePosition,
    TransportCharge,
    TransportEvent,
)
from services.student.models.student import Student, StudentStatus
from services.fee.models.fee import (
    FeeHead,
    FeeStructure,
    FeeLedger,
    FeeFrequency,
    FeeStatus,
)
from services.fee.schemas.fee import normalize_academic_year
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NepalCalendar, NPT

EXPIRIES = (
    "insurance_expiry_ad",
    "tax_expiry_ad",
    "fitness_expiry_ad",
    "permit_expiry_ad",
    "driver_license_expiry_ad",
)


def today():
    return datetime.now(NPT).date()


def now():
    return datetime.now(NPT)


def json_value(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value.value if hasattr(value, "value") else value


def fields(row, names):
    return {key: json_value(getattr(row, key)) for key in names.split()}


class TransportConflict(ValueError):
    pass


class TransportService:
    def __init__(self, db):
        self.db = db
        self.before = {}

    async def get(self, model, school, record_id, lock=False):
        query = select(model).where(model.school_id == school, model.id == record_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self.db.scalar(query)
        if row is None:
            raise RecordNotFoundError(model.__name__, str(record_id))
        return row

    async def command(
        self, action, school, data, actor, actor_name=None, resource=None
    ):
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"transport:{school}"},
        )
        payload = data.model_dump(mode="json", exclude={"request_id"}) | {
            "resource_id": str(resource) if resource else None
        }
        previous = await self.db.scalar(
            select(TransportEvent).where(
                TransportEvent.school_id == school,
                TransportEvent.request_id == data.request_id,
            )
        )
        if previous:
            if previous.action != action or previous.payload != payload:
                raise TransportConflict(
                    "This request ID was already used for different transport details"
                )
            return previous.result
        self.before = {}
        result = await getattr(self, f"_{action}")(school, data, resource)
        self.db.add(
            TransportEvent(
                id=uuid4(),
                school_id=school,
                request_id=data.request_id,
                action=action,
                actor_id=actor,
                actor_name=actor_name,
                payload=payload,
                result=result,
                before_values=self.before,
            )
        )
        await self.db.flush()
        return result

    async def page(self, query, page=1, limit=20):
        total = await self.db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        rows = (
            await self.db.scalars(query.offset((page - 1) * limit).limit(limit))
        ).all()
        return rows, total

    def vehicle_response(self, row):
        data = fields(
            row,
            "id vehicle_number vehicle_type capacity driver_name driver_phone driver_license helper_name helper_phone is_active gps_device_id condition insurance_expiry_ad tax_expiry_ad fitness_expiry_ad permit_expiry_ad driver_license_expiry_ad notes",
        )
        data["expired_documents"] = [
            field
            for field in EXPIRIES
            if getattr(row, field) and getattr(row, field) < today()
        ]
        data["missing_documents"] = [
            field for field in EXPIRIES if getattr(row, field) is None
        ]
        data["expiry_dates_bs"] = {
            field: NepalCalendar.ad_to_bs(getattr(row, field))
            if getattr(row, field)
            else None
            for field in EXPIRIES
        }
        return data

    def route_response(self, row):
        return fields(
            row,
            "id name start_point end_point description distance_km estimated_time_minutes pickup_fee drop_fee both_fee is_active",
        )

    def stop_response(self, row):
        return fields(
            row,
            "id route_id stop_name stop_order pickup_time drop_time latitude longitude pickup_fee drop_fee both_fee is_active notes",
        )

    def assignment_response(self, row):
        return fields(
            row,
            "id student_id route_id stop_id vehicle_id transport_type monthly_fee is_active pickup_run_id drop_run_id pickup_stop_id drop_stop_id start_date_ad end_date_ad needs_setup snapshot notes end_reason requires_handover handover_contact handover_phone previous_assignment_id",
        ) | {
            "start_date_bs": NepalCalendar.ad_to_bs(row.start_date_ad)
            if row.start_date_ad
            else None,
            "end_date_bs": NepalCalendar.ad_to_bs(row.end_date_ad)
            if row.end_date_ad
            else None,
        }

    def trip_response(self, row):
        return fields(
            row,
            "id run_id vehicle_id date_ad direction snapshot status started_at ended_at notes sweep_confirmed",
        ) | {"date_bs": NepalCalendar.ad_to_bs(row.date_ad)}

    async def _create_vehicle(self, school, data, resource):
        row = Vehicle(
            id=uuid4(),
            school_id=school,
            is_active=True,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(row)
        await self.db.flush()
        return self.vehicle_response(row)

    async def _update_vehicle(self, school, data, resource):
        row = await self.get(Vehicle, school, resource, True)
        runs = (
            await self.db.scalars(
                select(TransportRun).where(
                    TransportRun.school_id == school,
                    TransportRun.vehicle_id == row.id,
                    TransportRun.is_active.is_(True),
                )
            )
        ).all()
        if not data.is_active and runs:
            raise TransportConflict(
                "Archive or reassign active runs before archiving this vehicle"
            )
        counts = await self.loads(school, [run.id for run in runs])
        if max(counts.values(), default=0) > data.capacity:
            raise TransportConflict(
                "Vehicle capacity cannot be lower than its assigned run seats"
            )
        self.before = self.vehicle_response(row)
        for key, value in data.model_dump(exclude={"request_id"}).items():
            setattr(row, key, value)
        # Driver changes must not create a simultaneous duty on another vehicle.
        for run in runs:
            await self._schedule_check(school, run, row, run.id)
        await self.db.flush()
        return self.vehicle_response(row)

    async def _create_route(self, school, data, resource):
        row = Route(
            id=uuid4(),
            school_id=school,
            is_active=True,
            **data.model_dump(exclude={"request_id", "stops"}),
        )
        self.db.add(row)
        await self.db.flush()
        for number, stop in enumerate(data.stops, 1):
            self.db.add(
                RouteStop(
                    id=uuid4(),
                    school_id=school,
                    route_id=row.id,
                    stop_order=number,
                    is_active=True,
                    **stop.model_dump(),
                )
            )
        await self.db.flush()
        return self.route_response(row)

    async def _update_route(self, school, data, resource):
        row = await self.get(Route, school, resource, True)
        if not data.is_active:
            active_run = await self.db.scalar(
                select(TransportRun.id)
                .where(
                    TransportRun.school_id == school,
                    TransportRun.route_id == row.id,
                    TransportRun.is_active.is_(True),
                )
                .limit(1)
            )
            legacy = await self.db.scalar(
                select(StudentTransport.id)
                .where(
                    StudentTransport.school_id == school,
                    StudentTransport.route_id == row.id,
                    StudentTransport.is_active.is_(True),
                )
                .limit(1)
            )
            if active_run or legacy:
                raise TransportConflict(
                    "Reassign students and archive the route’s runs before archiving the route"
                )
        self.before = self.route_response(row)
        for key, value in data.model_dump(exclude={"request_id"}).items():
            setattr(row, key, value)
        await self.db.flush()
        return self.route_response(row)

    async def _create_stop(self, school, data, resource):
        route = await self.get(Route, school, resource, True)
        if not route.is_active:
            raise TransportConflict("Restore the route before adding stops")
        count = await self.db.scalar(
            select(func.count())
            .select_from(RouteStop)
            .where(
                RouteStop.school_id == school,
                RouteStop.route_id == route.id,
                RouteStop.is_active.is_(True),
            )
        )
        if count >= 200:
            raise ValueError("A route can have at most 200 active stops")
        order = await self.db.scalar(
            select(func.coalesce(func.max(RouteStop.stop_order), 0)).where(
                RouteStop.school_id == school,
                RouteStop.route_id == route.id,
                RouteStop.is_active.is_(True),
            )
        )
        row = RouteStop(
            id=uuid4(),
            school_id=school,
            route_id=route.id,
            stop_order=order + 1,
            is_active=True,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(row)
        await self.db.flush()
        return self.stop_response(row)

    async def _update_stop(self, school, data, resource):
        row = await self.get(RouteStop, school, resource, True)
        route = await self.get(Route, school, row.route_id)
        if data.is_active and not route.is_active:
            raise TransportConflict("Restore the route before activating a stop")
        if not data.is_active and await self.db.scalar(
            select(StudentTransport.id)
            .where(
                StudentTransport.school_id == school,
                StudentTransport.is_active.is_(True),
                or_(
                    StudentTransport.pickup_stop_id == row.id,
                    StudentTransport.drop_stop_id == row.id,
                    StudentTransport.stop_id == row.id,
                ),
            )
            .limit(1)
        ):
            raise TransportConflict(
                "Change or end student assignments before archiving this stop"
            )
        if data.is_active and not row.is_active:
            rows = (
                await self.db.scalars(
                    select(RouteStop).where(
                        RouteStop.school_id == school,
                        RouteStop.route_id == route.id,
                        RouteStop.is_active.is_(True),
                    )
                )
            ).all()
            if len(rows) >= 200:
                raise ValueError("A route can have at most 200 active stops")
            row.stop_order = max((item.stop_order for item in rows), default=0) + 1
        self.before = self.stop_response(row)
        for key, value in data.model_dump(exclude={"request_id"}).items():
            setattr(row, key, value)
        await self.db.flush()
        return self.stop_response(row)

    async def _reorder_stops(self, school, data, resource):
        await self.get(Route, school, resource, True)
        rows = (
            await self.db.scalars(
                select(RouteStop)
                .where(
                    RouteStop.school_id == school,
                    RouteStop.route_id == resource,
                    RouteStop.is_active.is_(True),
                )
                .with_for_update()
            )
        ).all()
        if {row.id for row in rows} != set(data.stop_ids):
            raise TransportConflict(
                "Reload and list every active route stop exactly once"
            )
        if [
            row.id for row in sorted(rows, key=lambda row: row.stop_order)
        ] != data.expected_stop_ids:
            raise TransportConflict(
                "Another staff member changed the stop order; reload before saving"
            )
        self.before = {
            "stop_ids": [
                str(row.id) for row in sorted(rows, key=lambda row: row.stop_order)
            ]
        }
        offset = max((row.stop_order for row in rows), default=0) + 1
        await self.db.execute(
            update(RouteStop)
            .where(RouteStop.id.in_(data.stop_ids), RouteStop.school_id == school)
            .values(stop_order=RouteStop.stop_order + offset)
            .execution_options(synchronize_session=False)
        )
        by_id = {row.id: row for row in rows}
        for number, stop_id in enumerate(data.stop_ids, 1):
            by_id[stop_id].stop_order = number
            # Mark ORM values dirty even when the old ordinal equals the new one.
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(by_id[stop_id], "stop_order")
        await self.db.flush()
        return {
            "route_id": str(resource),
            "stop_ids": [str(value) for value in data.stop_ids],
        }

    async def loads(self, school, ids):
        if not ids:
            return {}
        source = union_all(
            select(StudentTransport.pickup_run_id.label("run_id")).where(
                StudentTransport.school_id == school,
                StudentTransport.is_active.is_(True),
                StudentTransport.pickup_run_id.in_(ids),
            ),
            select(StudentTransport.drop_run_id.label("run_id")).where(
                StudentTransport.school_id == school,
                StudentTransport.is_active.is_(True),
                StudentTransport.drop_run_id.in_(ids),
            ),
        ).subquery()
        return dict(
            (
                await self.db.execute(
                    select(source.c.run_id, func.count()).group_by(source.c.run_id)
                )
            ).all()
        )

    async def _schedule_check(self, school, run, vehicle, exclude=None):
        query = (
            select(TransportRun, Vehicle)
            .join(Vehicle, Vehicle.id == TransportRun.vehicle_id)
            .where(
                TransportRun.school_id == school,
                Vehicle.school_id == school,
                TransportRun.is_active.is_(True),
                TransportRun.start_time < run.end_time,
                TransportRun.end_time > run.start_time,
            )
        )
        if exclude:
            query = query.where(TransportRun.id != exclude)
        for other, other_vehicle in (await self.db.execute(query)).all():
            same_driver = bool(
                vehicle.driver_license
                and other_vehicle.driver_license
                and vehicle.driver_license.strip().casefold()
                == other_vehicle.driver_license.strip().casefold()
            )
            if (other.vehicle_id == vehicle.id or same_driver) and set(
                other.weekdays
            ) & set(run.weekdays):
                raise TransportConflict(
                    "This vehicle or driver already has an overlapping run on an operating day"
                )

    async def _run_values(self, school, data, existing=None):
        route = await self.get(Route, school, data.route_id)
        vehicle = await self.get(Vehicle, school, data.vehicle_id)
        active = getattr(data, "is_active", True)
        if active and (
            not route.is_active
            or not vehicle.is_active
            or vehicle.condition != "available"
        ):
            raise TransportConflict(
                "Choose an active route and a vehicle available for service"
            )
        if existing:
            if await self.db.scalar(
                select(TransportTrip.id)
                .where(
                    TransportTrip.school_id == school,
                    TransportTrip.run_id == existing.id,
                    TransportTrip.status == "in_progress",
                )
                .limit(1)
            ):
                raise TransportConflict(
                    "Finish or cancel the current trip before editing its run"
                )
            seats = (await self.loads(school, [existing.id])).get(existing.id, 0)
            if seats and (
                not active
                or existing.route_id != data.route_id
                or existing.direction != data.direction
            ):
                raise TransportConflict(
                    "Change or end student assignments before archiving or changing this run’s route/direction"
                )
            if seats > vehicle.capacity:
                raise TransportConflict(
                    "The replacement vehicle does not have enough seats for this run"
                )
        if active:
            await self._schedule_check(
                school, data, vehicle, existing.id if existing else None
            )

    async def _create_run(self, school, data, resource):
        await self._run_values(school, data)
        row = TransportRun(
            id=uuid4(),
            school_id=school,
            is_active=True,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(row)
        await self.db.flush()
        return fields(
            row,
            "id name route_id vehicle_id direction start_time end_time weekdays is_active notes",
        )

    async def _update_run(self, school, data, resource):
        row = await self.get(TransportRun, school, resource, True)
        await self._run_values(school, data, row)
        self.before = fields(
            row,
            "name route_id vehicle_id direction start_time end_time weekdays is_active notes",
        )
        for key, value in data.model_dump(exclude={"request_id"}).items():
            setattr(row, key, value)
        await self.db.flush()
        return fields(
            row,
            "id name route_id vehicle_id direction start_time end_time weekdays is_active notes",
        )

    async def legs(self, school, data):
        result = {}
        for direction in ("pickup", "drop"):
            run_id = getattr(data, f"{direction}_run_id")
            if not run_id:
                continue
            run = await self.get(TransportRun, school, run_id)
            route = await self.get(Route, school, run.route_id)
            stop = await self.get(
                RouteStop, school, getattr(data, f"{direction}_stop_id")
            )
            vehicle = await self.get(Vehicle, school, run.vehicle_id)
            if run.direction != direction or stop.route_id != route.id:
                raise TransportConflict(
                    "The stop and direction must belong to the selected run’s route"
                )
            if (
                not run.is_active
                or not route.is_active
                or not stop.is_active
                or not vehicle.is_active
                or vehicle.condition != "available"
            ):
                raise TransportConflict(
                    "Choose active runs/stops with vehicles available for service"
                )
            result[direction] = {
                "run": run,
                "route": route,
                "stop": stop,
                "vehicle": vehicle,
            }
        return result

    def quote_legs(self, data, legs):
        kind = data.transport_type.value
        first = legs.get("pickup") or legs["drop"]
        if kind == "both" and (legs["pickup"]["stop"].id != legs["drop"]["stop"].id):
            return {"monthly_fee": None, "requires_agreed_price": True}
        stop_price = getattr(first["stop"], f"{kind}_fee")
        price = (
            stop_price
            if stop_price is not None
            else getattr(first["route"], f"{kind}_fee")
        )
        return {"monthly_fee": str(price), "requires_agreed_price": False}

    async def quote(self, school, data):
        return self.quote_legs(data, await self.legs(school, data))

    async def _student(self, school, student_id, lock=False, eligible=True):
        row = await self.get(Student, school, student_id, lock)
        if eligible and (
            row.status != StudentStatus.ACTIVE or row.is_deleted or row.deleted_at
        ):
            raise TransportConflict(
                "New assignments require an active enrolled student in this school"
            )
        return row

    async def _new_assignment(self, school, data, previous=None):
        student = await self._student(school, data.student_id, True)
        if await self.db.scalar(
            select(StudentTransport.id).where(
                StudentTransport.school_id == school,
                StudentTransport.student_id == student.id,
                StudentTransport.is_active.is_(True),
            )
        ):
            raise TransportConflict(
                "This student already has active transport; change or end the current assignment"
            )
        legs = await self.legs(school, data)
        counts = await self.loads(school, [leg["run"].id for leg in legs.values()])
        if any(
            counts.get(leg["run"].id, 0) >= leg["vehicle"].capacity
            for leg in legs.values()
        ):
            raise TransportConflict("A selected run has no available seats")
        quote = self.quote_legs(data, legs)
        if data.monthly_fee is None and quote["requires_agreed_price"]:
            raise ValueError(
                "Enter an agreed monthly charge when pickup and drop use different stops/routes"
            )
        price = (
            data.monthly_fee
            if data.monthly_fee is not None
            else Decimal(quote["monthly_fee"])
        )
        if (
            "drop" in legs
            and not data.requires_handover
            and (not data.notes or len(data.notes) < 3)
        ):
            raise ValueError(
                "Record the school’s arrangement when adult handover is not required"
            )
        if (
            quote["monthly_fee"] is None or price != Decimal(quote["monthly_fee"])
        ) and (not data.notes or len(data.notes) < 3):
            raise ValueError("Record a reason for the agreed price or rate override")
        first = legs.get("pickup") or legs["drop"]
        snapshot = {
            "student_name": student.full_name_en,
            "student_name_np": student.full_name_np,
            "reference": student.admission_number
            or student.emis_student_id
            or f'Grade {student.current_grade or "—"} {student.current_section or ""} · Roll {student.roll_number or "—"}',
        }
        for kind, leg in legs.items():
            snapshot[kind] = {
                "run_name": leg["run"].name,
                "route_name": leg["route"].name,
                "stop_name": leg["stop"].stop_name,
                "vehicle_number": leg["vehicle"].vehicle_number,
            }
        row = StudentTransport(
            id=uuid4(),
            school_id=school,
            route_id=first["route"].id,
            stop_id=first["stop"].id,
            vehicle_id=first["vehicle"].id,
            created_at=now(),
            start_date_ad=today(),
            is_active=True,
            needs_setup=False,
            snapshot=snapshot,
            previous_assignment_id=previous,
            **data.model_dump(exclude={"request_id", "monthly_fee"}),
            monthly_fee=price,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def _assign(self, school, data, resource):
        return self.assignment_response(await self._new_assignment(school, data))

    async def _endable(self, school, resource):
        row = await self.get(StudentTransport, school, resource, True)
        if not row.is_active:
            raise TransportConflict("This assignment has already ended")
        if await self.db.scalar(
            select(TransportPassenger.id)
            .join(TransportTrip, TransportTrip.id == TransportPassenger.trip_id)
            .where(
                TransportPassenger.school_id == school,
                TransportTrip.school_id == school,
                TransportPassenger.assignment_id == row.id,
                TransportTrip.status == "in_progress",
            )
            .limit(1)
        ):
            raise TransportConflict(
                "Finish the current trip before changing or ending this student’s assignment"
            )
        return row

    async def _end_assignment(self, school, data, resource):
        row = await self._endable(school, resource)
        self.before = self.assignment_response(row)
        row.is_active, row.end_date_ad, row.end_reason = False, today(), data.notes
        await self.db.flush()
        return self.assignment_response(row)

    async def _change_assignment(self, school, data, resource):
        row = await self._endable(school, resource)
        if row.student_id != data.student_id:
            raise ValueError("Changing an assignment must retain the same student")
        if not data.notes or len(data.notes) < 3:
            raise ValueError("Record the reason for the transport change")
        self.before = self.assignment_response(row)
        row.is_active, row.end_date_ad, row.end_reason = False, today(), data.notes
        await self.db.flush()
        return self.assignment_response(
            await self._new_assignment(school, data, row.id)
        )

    async def _start_trip(self, school, data, resource):
        run = await self.get(TransportRun, school, data.run_id, True)
        vehicle = await self.get(Vehicle, school, run.vehicle_id, True)
        route = await self.get(Route, school, run.route_id)
        if (
            not run.is_active
            or not route.is_active
            or not vehicle.is_active
            or vehicle.condition != "available"
        ):
            raise TransportConflict(
                "The run, route and vehicle must be active and available"
            )
        if (today().weekday() + 1) % 7 not in run.weekdays:
            raise TransportConflict("This run is not scheduled to operate today")
        if not vehicle.driver_name:
            raise TransportConflict("Record the driver’s name before dispatch")
        if vehicle.driver_license and await self.db.scalar(
            select(TransportTrip.id)
            .where(
                TransportTrip.school_id == school,
                TransportTrip.status == "in_progress",
                func.lower(func.btrim(TransportTrip.snapshot["driver_license"].astext))
                == vehicle.driver_license.strip().casefold(),
            )
            .limit(1)
        ):
            raise TransportConflict(
                "The recorded driver is still on another trip; close that trip before dispatch"
            )
        expired = self.vehicle_response(vehicle)["expired_documents"]
        if expired:
            raise TransportConflict(
                "Update expired recorded vehicle/driver documents before dispatch: "
                + ", ".join(
                    name.replace("_expiry_ad", "").replace("_", " ") for name in expired
                )
            )
        if await self.db.scalar(
            select(TransportTrip.id)
            .where(
                TransportTrip.school_id == school,
                or_(
                    (TransportTrip.run_id == run.id)
                    & (TransportTrip.date_ad == today())
                    & (TransportTrip.status != "cancelled"),
                    (TransportTrip.vehicle_id == vehicle.id)
                    & (TransportTrip.status == "in_progress"),
                ),
            )
            .limit(1)
        ):
            raise TransportConflict(
                "This run already has a trip today, or the vehicle is still on another trip"
            )
        run_column = (
            StudentTransport.pickup_run_id
            if run.direction == "pickup"
            else StudentTransport.drop_run_id
        )
        stop_column = (
            StudentTransport.pickup_stop_id
            if run.direction == "pickup"
            else StudentTransport.drop_stop_id
        )
        rows = (
            await self.db.execute(
                select(StudentTransport, RouteStop, Student)
                .join(RouteStop, RouteStop.id == stop_column)
                .join(Student, Student.id == StudentTransport.student_id)
                .where(
                    StudentTransport.school_id == school,
                    RouteStop.school_id == school,
                    Student.school_id == school,
                    run_column == run.id,
                    StudentTransport.is_active.is_(True),
                    StudentTransport.needs_setup.is_(False),
                    RouteStop.is_active.is_(True),
                    Student.status == StudentStatus.ACTIVE,
                    Student.is_deleted.is_(False),
                    Student.deleted_at.is_(None),
                )
                .order_by(RouteStop.stop_order, Student.full_name_en)
            )
        ).all()
        if not rows:
            raise TransportConflict(
                "No eligible assigned students are available for this trip"
            )
        if len(rows) > vehicle.capacity:
            raise TransportConflict(
                "This trip would exceed the vehicle passenger capacity"
            )
        trip = TransportTrip(
            id=uuid4(),
            school_id=school,
            run_id=run.id,
            vehicle_id=vehicle.id,
            date_ad=today(),
            direction=run.direction,
            status="in_progress",
            started_at=now(),
            sweep_confirmed=False,
            notes=data.notes,
            snapshot={
                "run_name": run.name,
                "route_name": route.name,
                "vehicle_number": vehicle.vehicle_number,
                "driver_name": vehicle.driver_name,
                "driver_license": vehicle.driver_license,
                "driver_phone": vehicle.driver_phone,
                "helper_name": vehicle.helper_name,
                "helper_phone": vehicle.helper_phone,
                "capacity": vehicle.capacity,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat(),
            },
        )
        self.db.add(trip)
        await self.db.flush()
        self.db.add_all(
            [
                TransportPassenger(
                    id=uuid4(),
                    school_id=school,
                    trip_id=trip.id,
                    assignment_id=assignment.id,
                    student_id=student.id,
                    student_name=student.full_name_en,
                    reference=student.admission_number
                    or student.emis_student_id
                    or assignment.snapshot.get("reference"),
                    stop_name=stop.stop_name,
                    stop_order=stop.stop_order,
                    requires_handover=run.direction == "drop"
                    and assignment.requires_handover,
                    status="pending",
                    version=1,
                )
                for assignment, stop, student in rows
            ]
        )
        await self.db.flush()
        return self.trip_response(trip)

    async def _passenger(self, school, data, resource):
        row = await self.get(TransportPassenger, school, resource, True)
        trip = await self.get(TransportTrip, school, row.trip_id, True)
        if trip.status != "in_progress":
            raise TransportConflict(
                "This trip is closed; its boarding records cannot be changed"
            )
        if row.version != data.version:
            raise TransportConflict(
                "Another staff member updated this passenger; reload before recording a change"
            )
        allowed = {"pending": {"boarded", "absent"}, "boarded": {"alighted"}}
        if data.status not in allowed.get(row.status, set()):
            raise TransportConflict(
                "Record boarding before alighting; completed/absent passengers cannot be marked again"
            )
        if data.status == "absent" and (not data.notes or len(data.notes) < 3):
            raise ValueError("Record the absence reason or follow-up note")
        if (
            data.status == "alighted"
            and row.requires_handover
            and (not data.received_by or len(data.received_by) < 2)
        ):
            raise ValueError(
                "Record the responsible adult who received the student at home drop"
            )
        self.before = fields(row, "status version received_by notes")
        row.status, row.notes, row.received_by = (
            data.status,
            data.notes,
            data.received_by,
        )
        row.version += 1
        if data.status == "boarded":
            row.boarded_at = now()
        if data.status == "alighted":
            row.alighted_at = now()
        await self.db.flush()
        return fields(
            row,
            "id trip_id student_name status version boarded_at alighted_at received_by notes",
        )

    async def _complete_trip(self, school, data, resource):
        row = await self.get(TransportTrip, school, resource, True)
        if row.status != "in_progress":
            raise TransportConflict("This trip has already been closed")
        unfinished = await self.db.scalar(
            select(func.count())
            .select_from(TransportPassenger)
            .where(
                TransportPassenger.school_id == school,
                TransportPassenger.trip_id == row.id,
                TransportPassenger.status.in_(("pending", "boarded")),
            )
        )
        if unfinished:
            raise TransportConflict(
                "Resolve every pending/on-board passenger before completing the trip"
            )
        self.before = {"status": row.status}
        row.status, row.ended_at, row.sweep_confirmed, row.notes = (
            "completed",
            now(),
            data.sweep_confirmed,
            data.notes,
        )
        await self.db.flush()
        return self.trip_response(row)

    async def _cancel_trip(self, school, data, resource):
        row = await self.get(TransportTrip, school, resource, True)
        if row.status != "in_progress":
            raise TransportConflict("This trip has already been closed")
        if await self.db.scalar(
            select(TransportPassenger.id)
            .where(
                TransportPassenger.school_id == school,
                TransportPassenger.trip_id == row.id,
                TransportPassenger.status.in_(("boarded", "alighted")),
            )
            .limit(1)
        ):
            raise TransportConflict(
                "A trip with boarded passengers must be resolved and completed, not cancelled"
            )
        row.status, row.ended_at, row.notes = "cancelled", now(), data.notes
        await self.db.execute(
            update(TransportPassenger)
            .where(
                TransportPassenger.school_id == school,
                TransportPassenger.trip_id == row.id,
                TransportPassenger.status == "pending",
            )
            .values(status="cancelled", version=TransportPassenger.version + 1)
        )
        await self.db.flush()
        return self.trip_response(row)

    async def _maintenance(self, school, data, resource):
        await self.get(Vehicle, school, resource)
        if (
            data.service_date_ad > today()
            or data.next_due_ad
            and data.next_due_ad < data.service_date_ad
        ):
            raise ValueError(
                "Service date cannot be in the future, and next due must follow the service date"
            )
        NepalCalendar.ad_to_bs(data.service_date_ad)
        if data.next_due_ad:
            NepalCalendar.ad_to_bs(data.next_due_ad)
        row = TransportMaintenance(
            id=uuid4(),
            school_id=school,
            vehicle_id=resource,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(row)
        await self.db.flush()
        return fields(
            row,
            "id vehicle_id service_date_ad kind odometer_km cost next_due_ad vendor notes",
        )

    async def _position(self, school, data, resource):
        await self.get(Vehicle, school, resource)
        if data.recorded_at < now() - timedelta(
            minutes=15
        ) or data.recorded_at > now() + timedelta(seconds=30):
            raise ValueError(
                "Report a current position, within the last 15 minutes and without a future timestamp"
            )
        row = VehiclePosition(
            id=uuid4(),
            school_id=school,
            vehicle_id=resource,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(row)
        await self.db.flush()
        return fields(
            row, "id vehicle_id latitude longitude accuracy_m recorded_at source"
        )

    async def vehicles(self, school, page=1, search=None, is_active=True):
        query = select(Vehicle).where(
            Vehicle.school_id == school, Vehicle.is_active == is_active
        )
        if search:
            query = query.where(
                or_(
                    Vehicle.vehicle_number.ilike(f"%{search}%"),
                    Vehicle.driver_name.ilike(f"%{search}%"),
                    Vehicle.helper_name.ilike(f"%{search}%"),
                )
            )
        rows, total = await self.page(
            query.order_by(Vehicle.vehicle_number, Vehicle.id), page
        )
        return {
            "vehicles": [self.vehicle_response(row) for row in rows],
            "total": total,
        }

    async def routes(self, school, page=1, search=None, is_active=True):
        query = select(Route).where(
            Route.school_id == school, Route.is_active == is_active
        )
        if search:
            query = query.where(
                or_(
                    Route.name.ilike(f"%{search}%"),
                    Route.start_point.ilike(f"%{search}%"),
                    Route.end_point.ilike(f"%{search}%"),
                )
            )
        rows, total = await self.page(query.order_by(Route.name, Route.id), page)
        counts = (
            dict(
                (
                    await self.db.execute(
                        select(RouteStop.route_id, func.count())
                        .where(
                            RouteStop.school_id == school,
                            RouteStop.route_id.in_([row.id for row in rows]),
                            RouteStop.is_active.is_(True),
                        )
                        .group_by(RouteStop.route_id)
                    )
                ).all()
            )
            if rows
            else {}
        )
        return {
            "routes": [
                self.route_response(row) | {"stop_count": counts.get(row.id, 0)}
                for row in rows
            ],
            "total": total,
        }

    async def route(self, school, route_id):
        row = await self.get(Route, school, route_id)
        stops = (
            await self.db.scalars(
                select(RouteStop)
                .where(RouteStop.school_id == school, RouteStop.route_id == row.id)
                .order_by(
                    RouteStop.is_active.desc(), RouteStop.stop_order, RouteStop.id
                )
            )
        ).all()
        return self.route_response(row) | {
            "stops": [self.stop_response(stop) for stop in stops]
        }

    async def runs(
        self,
        school,
        page=1,
        search=None,
        is_active=True,
        direction=None,
        route_id=None,
        vehicle_id=None,
    ):
        query = (
            select(TransportRun)
            .join(Route, Route.id == TransportRun.route_id)
            .join(Vehicle, Vehicle.id == TransportRun.vehicle_id)
            .where(
                TransportRun.school_id == school,
                Route.school_id == school,
                Vehicle.school_id == school,
                TransportRun.is_active == is_active,
            )
        )
        if direction:
            query = query.where(TransportRun.direction == direction)
        if route_id:
            query = query.where(TransportRun.route_id == route_id)
        if vehicle_id:
            query = query.where(TransportRun.vehicle_id == vehicle_id)
        if search:
            query = query.where(
                or_(
                    TransportRun.name.ilike(f"%{search}%"),
                    Route.name.ilike(f"%{search}%"),
                    Vehicle.vehicle_number.ilike(f"%{search}%"),
                )
            )
        rows, total = await self.page(
            query.order_by(TransportRun.start_time, TransportRun.name, TransportRun.id),
            page,
        )
        counts = await self.loads(school, [row.id for row in rows])
        vehicles = (
            {
                row.id: row
                for row in (
                    await self.db.scalars(
                        select(Vehicle).where(
                            Vehicle.school_id == school,
                            Vehicle.id.in_([row.vehicle_id for row in rows]),
                        )
                    )
                ).all()
            }
            if rows
            else {}
        )
        routes = (
            {
                row.id: row
                for row in (
                    await self.db.scalars(
                        select(Route).where(
                            Route.school_id == school,
                            Route.id.in_([row.route_id for row in rows]),
                        )
                    )
                ).all()
            }
            if rows
            else {}
        )
        return {
            "runs": [
                fields(
                    row,
                    "id name route_id vehicle_id direction start_time end_time weekdays is_active notes",
                )
                | {
                    "vehicle_number": vehicles[row.vehicle_id].vehicle_number,
                    "route_name": routes[row.route_id].name,
                    "capacity": vehicles[row.vehicle_id].capacity,
                    "assigned_seats": counts.get(row.id, 0),
                    "available_seats": max(
                        0, vehicles[row.vehicle_id].capacity - counts.get(row.id, 0)
                    ),
                    "vehicle_condition": vehicles[row.vehicle_id].condition,
                    "dispatch_issues": self.vehicle_response(vehicles[row.vehicle_id])[
                        "expired_documents"
                    ],
                    "driver_name": vehicles[row.vehicle_id].driver_name,
                }
                for row in rows
            ],
            "total": total,
        }

    async def students(self, school, page=1, search=None):
        query = select(
            Student.id,
            Student.full_name_en,
            Student.full_name_np,
            Student.admission_number,
            Student.emis_student_id,
            Student.current_grade,
            Student.current_section,
            Student.roll_number,
        ).where(
            Student.school_id == school,
            Student.status == StudentStatus.ACTIVE,
            Student.is_deleted.is_(False),
            Student.deleted_at.is_(None),
        )
        if search:
            query = query.where(
                or_(
                    Student.full_name_en.ilike(f"%{search}%"),
                    Student.full_name_np.ilike(f"%{search}%"),
                    Student.admission_number.ilike(f"%{search}%"),
                    Student.emis_student_id.ilike(f"%{search}%"),
                )
            )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            await self.db.execute(
                query.order_by(Student.full_name_en, Student.id)
                .offset((page - 1) * 20)
                .limit(20)
            )
        ).all()
        assigned = (
            dict(
                (
                    await self.db.execute(
                        select(StudentTransport.student_id, StudentTransport.id).where(
                            StudentTransport.school_id == school,
                            StudentTransport.student_id.in_([row.id for row in rows]),
                            StudentTransport.is_active.is_(True),
                        )
                    )
                ).all()
            )
            if rows
            else {}
        )
        return {
            "students": [
                {key: json_value(value) for key, value in row._mapping.items()}
                | {
                    "active_assignment_id": str(assigned[row.id])
                    if row.id in assigned
                    else None
                }
                for row in rows
            ],
            "total": total,
        }

    def assignments_query(
        self, school, search=None, is_active=True, run_id=None, route_id=None
    ):
        query = select(StudentTransport).where(
            StudentTransport.school_id == school,
            StudentTransport.is_active == is_active,
        )
        if run_id:
            query = query.where(
                or_(
                    StudentTransport.pickup_run_id == run_id,
                    StudentTransport.drop_run_id == run_id,
                )
            )
        if route_id:
            ids = select(TransportRun.id).where(
                TransportRun.school_id == school, TransportRun.route_id == route_id
            )
            query = query.where(
                or_(
                    StudentTransport.route_id == route_id,
                    StudentTransport.pickup_run_id.in_(ids),
                    StudentTransport.drop_run_id.in_(ids),
                )
            )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    StudentTransport.snapshot["student_name"].astext.ilike(pattern),
                    StudentTransport.snapshot["reference"].astext.ilike(pattern),
                    StudentTransport.snapshot["pickup"]["route_name"].astext.ilike(
                        pattern
                    ),
                    StudentTransport.snapshot["drop"]["route_name"].astext.ilike(
                        pattern
                    ),
                    StudentTransport.snapshot["route_name"].astext.ilike(pattern),
                )
            )
        return query.order_by(StudentTransport.created_at.desc(), StudentTransport.id)

    async def assignments(self, school, page=1, **filters):
        rows, total = await self.page(self.assignments_query(school, **filters), page)
        return {
            "assignments": [self.assignment_response(row) for row in rows],
            "total": total,
        }

    async def trips(self, school, page=1, day=None, status=None, run_id=None):
        query = select(TransportTrip).where(TransportTrip.school_id == school)
        if day:
            query = query.where(TransportTrip.date_ad == day)
        if status:
            query = query.where(TransportTrip.status == status)
        if run_id:
            query = query.where(TransportTrip.run_id == run_id)
        rows, total = await self.page(
            query.order_by(TransportTrip.started_at.desc(), TransportTrip.id), page
        )
        return {"trips": [self.trip_response(row) for row in rows], "total": total}

    async def trip(self, school, trip_id, page=1, limit=20):
        row = await self.get(TransportTrip, school, trip_id)
        query = select(TransportPassenger).where(
            TransportPassenger.school_id == school, TransportPassenger.trip_id == row.id
        )
        passengers, total = await self.page(
            query.order_by(
                TransportPassenger.stop_order,
                TransportPassenger.student_name,
                TransportPassenger.id,
            ),
            page,
            limit,
        )
        counts = dict(
            (
                await self.db.execute(
                    select(TransportPassenger.status, func.count())
                    .where(
                        TransportPassenger.school_id == school,
                        TransportPassenger.trip_id == row.id,
                    )
                    .group_by(TransportPassenger.status)
                )
            ).all()
        )
        return {
            "trip": self.trip_response(row),
            "passengers": [
                fields(
                    item,
                    "id trip_id assignment_id student_id student_name reference stop_name stop_order requires_handover status boarded_at alighted_at received_by notes version",
                )
                for item in passengers
            ],
            "total": total,
            "counts": counts,
        }

    async def maintenance(self, school, vehicle_id, page=1):
        await self.get(Vehicle, school, vehicle_id)
        rows, total = await self.page(
            select(TransportMaintenance)
            .where(
                TransportMaintenance.school_id == school,
                TransportMaintenance.vehicle_id == vehicle_id,
            )
            .order_by(
                TransportMaintenance.service_date_ad.desc(), TransportMaintenance.id
            ),
            page,
        )
        return {
            "records": [
                fields(
                    row,
                    "id vehicle_id service_date_ad kind odometer_km cost next_due_ad vendor notes",
                )
                | {
                    "service_date_bs": NepalCalendar.ad_to_bs(row.service_date_ad),
                    "next_due_bs": NepalCalendar.ad_to_bs(row.next_due_ad)
                    if row.next_due_ad
                    else None,
                }
                for row in rows
            ],
            "total": total,
        }

    async def location(self, school, vehicle_id):
        await self.get(Vehicle, school, vehicle_id)
        row = await self.db.scalar(
            select(VehiclePosition)
            .where(
                VehiclePosition.school_id == school,
                VehiclePosition.vehicle_id == vehicle_id,
            )
            .order_by(VehiclePosition.recorded_at.desc(), VehiclePosition.id)
            .limit(1)
        )
        if row is None:
            return {"position": None}
        age = max(0, int((now() - row.recorded_at).total_seconds()))
        return {
            "position": fields(
                row, "id vehicle_id latitude longitude accuracy_m recorded_at source"
            )
            | {"age_seconds": age, "stale": age > 120}
        }

    async def fee_options(self, school, assignment_id, month):
        assignment = await self.get(StudentTransport, school, assignment_id)
        student = await self._student(school, assignment.student_id, eligible=False)
        year = normalize_academic_year(month[:4])
        rows = (
            await self.db.execute(
                select(
                    FeeHead.id,
                    FeeHead.name,
                    FeeHead.amount,
                    FeeStructure.name.label("structure_name"),
                )
                .join(FeeStructure, FeeStructure.id == FeeHead.fee_structure_id)
                .where(
                    FeeStructure.school_id == school,
                    FeeStructure.grade == str(student.current_grade),
                    FeeStructure.academic_year_bs == year,
                    FeeStructure.is_active.is_(True),
                    FeeHead.is_optional.is_(True),
                    FeeHead.frequency == FeeFrequency.monthly,
                )
                .order_by(FeeHead.name)
            )
        ).all()
        return {
            "academic_year_bs": year,
            "monthly_fee": str(assignment.monthly_fee),
            "options": [
                {key: json_value(value) for key, value in row._mapping.items()}
                for row in rows
            ],
        }

    async def _bill(self, school, data, resource):
        assignment = await self.get(StudentTransport, school, resource)
        if assignment.needs_setup:
            raise TransportConflict(
                "Reconcile the legacy transport assignment before posting through this workflow"
            )
        start = NepalCalendar.bs_to_ad(f"{data.month_bs}-01")
        year, month = map(int, data.month_bs.split("-"))
        end = NepalCalendar.bs_to_ad(
            f"{year+1 if month==12 else year}-{1 if month==12 else month+1:02d}-01"
        ) - timedelta(days=1)
        if (
            assignment.start_date_ad > end
            or assignment.end_date_ad
            and assignment.end_date_ad < start
        ):
            raise ValueError("This assignment does not cover the selected BS month")
        if start > today():
            raise ValueError(
                "Post transport bills for the current or an earlier BS month"
            )
        head = await self.db.scalar(
            select(FeeHead)
            .join(FeeStructure, FeeStructure.id == FeeHead.fee_structure_id)
            .where(FeeHead.id == data.fee_head_id, FeeStructure.school_id == school)
        )
        if head is None:
            raise RecordNotFoundError("FeeHead", str(data.fee_head_id))
        structure = await self.get(FeeStructure, school, head.fee_structure_id, True)
        await self._student(school, assignment.student_id, True, eligible=False)
        student = await self.get(Student, school, assignment.student_id)
        await self.db.refresh(head)
        if (
            not structure.is_active
            or structure.grade != str(student.current_grade)
            or structure.academic_year_bs != normalize_academic_year(str(year))
        ):
            raise ValueError(
                "Choose an active fee structure matching the student grade and BS year"
            )
        if (
            not head.is_optional
            or head.frequency != FeeFrequency.monthly
            or head.amount != assignment.monthly_fee
            or assignment.monthly_fee <= 0
        ):
            raise ValueError(
                "Select an optional monthly transport fee head matching the agreed charge"
            )
        charge = await self.db.scalar(
            select(TransportCharge).where(
                TransportCharge.school_id == school,
                TransportCharge.student_id == assignment.student_id,
                TransportCharge.month_bs == data.month_bs,
            )
        )
        if charge:
            ledger = await self.get(FeeLedger, school, charge.ledger_id)
            if (
                ledger.fee_head_id != head.id
                or ledger.original_amount != assignment.monthly_fee
            ):
                raise TransportConflict(
                    "This student already has a transport bill for this BS month; review it in Fees & Payments"
                )
            return {
                "ledger_id": str(ledger.id),
                "month_bs": data.month_bs,
                "amount": str(ledger.original_amount),
                "already_billed": True,
                "student_name": assignment.snapshot.get("student_name"),
            }
        due = NepalCalendar.bs_to_ad(f"{data.month_bs}-{data.due_day_bs:02d}")
        ledger_id = (
            await self.db.execute(
                pg_insert(FeeLedger)
                .values(
                    id=uuid4(),
                    school_id=school,
                    student_id=assignment.student_id,
                    fee_head_id=head.id,
                    fee_head_name=head.name,
                    academic_year_bs=structure.academic_year_bs,
                    month_bs=data.month_bs,
                    original_amount=head.amount,
                    discount_amount=0,
                    amount_due=head.amount,
                    amount_paid=0,
                    balance=head.amount,
                    due_date_ad=due,
                    status=FeeStatus.overdue if due < today() else FeeStatus.pending,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "school_id",
                        "student_id",
                        "fee_head_id",
                        "academic_year_bs",
                        text("coalesce(month_bs, '')"),
                    ]
                )
                .returning(FeeLedger.id)
            )
        ).scalar_one_or_none()
        already = ledger_id is None
        if already:
            ledger = await self.db.scalar(
                select(FeeLedger).where(
                    FeeLedger.school_id == school,
                    FeeLedger.student_id == assignment.student_id,
                    FeeLedger.fee_head_id == head.id,
                    FeeLedger.academic_year_bs == structure.academic_year_bs,
                    FeeLedger.month_bs == data.month_bs,
                )
            )
            if ledger.original_amount != assignment.monthly_fee:
                raise TransportConflict(
                    "The existing fee bill has a different original amount"
                )
            ledger_id = ledger.id
        self.db.add(
            TransportCharge(
                id=uuid4(),
                school_id=school,
                assignment_id=assignment.id,
                student_id=assignment.student_id,
                month_bs=data.month_bs,
                ledger_id=ledger_id,
            )
        )
        await self.db.flush()
        return {
            "ledger_id": str(ledger_id),
            "month_bs": data.month_bs,
            "amount": str(head.amount),
            "already_billed": already,
            "student_name": assignment.snapshot.get("student_name"),
        }

    async def stats(self, school):
        total, available, maintenance, expired = (
            await self.db.execute(
                select(
                    func.count(),
                    func.count().filter(Vehicle.condition == "available"),
                    func.count().filter(Vehicle.condition == "maintenance"),
                    func.count().filter(
                        or_(*(getattr(Vehicle, key) < today() for key in EXPIRIES))
                    ),
                ).where(Vehicle.school_id == school, Vehicle.is_active.is_(True))
            )
        ).one()
        assigned, legacy = (
            await self.db.execute(
                select(
                    func.count(),
                    func.count().filter(StudentTransport.needs_setup.is_(True)),
                ).where(
                    StudentTransport.school_id == school,
                    StudentTransport.is_active.is_(True),
                )
            )
        ).one()
        trip_counts = dict(
            (
                await self.db.execute(
                    select(TransportTrip.status, func.count())
                    .where(
                        TransportTrip.school_id == school,
                        TransportTrip.date_ad == today(),
                    )
                    .group_by(TransportTrip.status)
                )
            ).all()
        )
        return {
            "total_vehicles": total,
            "available_vehicles": available,
            "maintenance_vehicles": maintenance,
            "expired_document_vehicles": expired,
            "total_routes": await self.db.scalar(
                select(func.count())
                .select_from(Route)
                .where(Route.school_id == school, Route.is_active.is_(True))
            ),
            "total_runs": await self.db.scalar(
                select(func.count())
                .select_from(TransportRun)
                .where(
                    TransportRun.school_id == school, TransportRun.is_active.is_(True)
                )
            ),
            "students_using": assigned,
            "needs_setup": legacy,
            "today_trips": trip_counts,
            "active_trips": await self.db.scalar(
                select(func.count())
                .select_from(TransportTrip)
                .where(
                    TransportTrip.school_id == school,
                    TransportTrip.status == "in_progress",
                )
            ),
            "date_ad": today().isoformat(),
            "date_bs": NepalCalendar.ad_to_bs(today()),
        }

    async def history(self, school, page=1):
        rows, total = await self.page(
            select(TransportEvent)
            .where(TransportEvent.school_id == school)
            .order_by(TransportEvent.created_at.desc(), TransportEvent.id),
            page,
        )
        public = {
            "name",
            "vehicle_number",
            "student_name",
            "status",
            "condition",
            "capacity",
            "monthly_fee",
            "direction",
            "stop_name",
            "start_time",
            "end_time",
            "weekdays",
            "is_active",
            "received_by",
            "version",
            "kind",
            "cost",
            "source",
            "recorded_at",
            "month_bs",
            "amount",
            "already_billed",
        }
        return {
            "events": [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "actor_name": row.actor_name,
                    "created_at": row.created_at.isoformat(),
                    "notes": row.payload.get("notes"),
                    "label": row.result.get("name")
                    or row.result.get("student_name")
                    or row.result.get("vehicle_number")
                    or row.result.get("snapshot", {}).get("student_name")
                    or row.result.get("snapshot", {}).get("run_name"),
                    "before": {
                        key: value
                        for key, value in row.before_values.items()
                        if key in public
                    },
                    "after": {
                        key: value for key, value in row.result.items() if key in public
                    },
                }
                for row in rows
            ],
            "total": total,
        }

    async def export(
        self, school, report, search=None, is_active=True, run_id=None, trip_id=None
    ):
        if report == "assignments":
            rows = (
                await self.db.scalars(
                    self.assignments_query(school, search, is_active, run_id).limit(
                        50_001
                    )
                )
            ).all()
            header = [
                "Student",
                "Reference",
                "Service",
                "Pickup route",
                "Pickup stop",
                "Drop route",
                "Drop stop",
                "Agreed NPR/month",
                "Start BS",
                "End BS",
                "Active",
                "Needs setup",
            ]
            values = [
                (
                    r.snapshot.get("student_name"),
                    r.snapshot.get("reference"),
                    r.transport_type.value,
                    r.snapshot.get("pickup", {}).get(
                        "route_name", r.snapshot.get("route_name")
                    ),
                    r.snapshot.get("pickup", {}).get(
                        "stop_name", r.snapshot.get("stop_name")
                    ),
                    r.snapshot.get("drop", {}).get("route_name"),
                    r.snapshot.get("drop", {}).get("stop_name"),
                    r.monthly_fee,
                    NepalCalendar.ad_to_bs(r.start_date_ad) if r.start_date_ad else "",
                    NepalCalendar.ad_to_bs(r.end_date_ad) if r.end_date_ad else "",
                    r.is_active,
                    r.needs_setup,
                )
                for r in rows
            ]
        else:
            trip = await self.get(TransportTrip, school, trip_id)
            rows = (
                await self.db.scalars(
                    select(TransportPassenger)
                    .where(
                        TransportPassenger.school_id == school,
                        TransportPassenger.trip_id == trip.id,
                    )
                    .order_by(
                        TransportPassenger.stop_order,
                        TransportPassenger.student_name,
                        TransportPassenger.id,
                    )
                    .limit(50_001)
                )
            ).all()
            header = [
                "Date BS",
                "Date AD",
                "Run",
                "Vehicle",
                "Direction",
                "Student",
                "Reference",
                "Stop",
                "Status",
                "Boarded at",
                "Alighted at",
                "Received by",
                "Notes",
            ]
            values = [
                (
                    NepalCalendar.ad_to_bs(trip.date_ad),
                    trip.date_ad,
                    trip.snapshot.get("run_name"),
                    trip.snapshot.get("vehicle_number"),
                    trip.direction,
                    r.student_name,
                    r.reference,
                    r.stop_name,
                    r.status,
                    r.boarded_at,
                    r.alighted_at,
                    r.received_by,
                    r.notes,
                )
                for r in rows
            ]
        if len(rows) > 50_000:
            raise ValueError(
                "Narrow the filters before exporting more than 50,000 records"
            )
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(header)

        def safe(value):
            value = "" if value is None else str(value)
            return (
                "'" + value
                if value.lstrip().startswith(("=", "+", "-", "@"))
                else value
            )

        writer.writerows([[safe(value) for value in row] for row in values])
        return ("\ufeff" + stream.getvalue()).encode("utf-8")
