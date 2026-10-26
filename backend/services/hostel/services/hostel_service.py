"""School-scoped hostel operations, physical inventory and auditable registers."""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from services.hostel.models.hostel import (
    Hostel,
    Room,
    RoomAllocation,
    HostelBed,
    HostelLeave,
    HostelVisit,
    HostelRegister,
    HostelCharge,
    HostelEvent,
    AllocationStatus,
    HostelType,
)
from services.student.models.student import Student, StudentStatus, Gender
from services.fee.models.fee import (
    FeeHead,
    FeeStructure,
    FeeLedger,
    FeeFrequency,
    FeeStatus,
)
from services.fee.schemas.fee import normalize_academic_year
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NPT, NepalCalendar


def today():
    return datetime.now(NPT).date()


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value.value if hasattr(value, "value") else value


def fields(row, names):
    return {name: json_value(getattr(row, name)) for name in names.split()}


class HostelConflict(ValueError):
    pass


class HostelService:
    def __init__(self, db):
        self.db = db
        self.before = {}
        self.stay_id = None

    async def get(self, model, school_id, record_id, lock=False):
        query = select(model).where(model.school_id == school_id, model.id == record_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        record = await self.db.scalar(query)
        if record is None:
            raise RecordNotFoundError(model.__name__, str(record_id))
        return record

    async def command(
        self, action, school_id, data, actor_id, actor_name=None, resource_id=None
    ):
        # Short, bounded hostel writes serialize per school. Unique active-bed and
        # student constraints remain a second guard against conflicting writes.
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"hostel:{school_id}"},
        )
        payload = data.model_dump(mode="json", exclude={"request_id"}) | {
            "resource_id": str(resource_id) if resource_id else None
        }
        previous = await self.db.scalar(
            select(HostelEvent).where(
                HostelEvent.school_id == school_id,
                HostelEvent.request_id == data.request_id,
            )
        )
        if previous:
            if previous.action != action or previous.payload != payload:
                raise HostelConflict(
                    "This request ID was already used for different hostel details"
                )
            return previous.result
        self.before, self.stay_id = {}, None
        result = await getattr(self, f"_{action}")(
            school_id, data, resource_id, actor_id
        )
        self.db.add(
            HostelEvent(
                id=uuid4(),
                school_id=school_id,
                request_id=data.request_id,
                action=action,
                allocation_id=self.stay_id,
                actor_id=actor_id,
                actor_name=actor_name,
                payload=payload,
                result=result,
                before_values=self.before,
            )
        )
        await self.db.flush()
        return result

    def hostel_response(self, row):
        return fields(
            row,
            "id name hostel_type warden_name warden_phone address notes total_rooms capacity is_active",
        )

    def room_response(self, row):
        return fields(
            row,
            "id hostel_id room_number floor capacity occupied room_type monthly_fee is_active notes",
        )

    def stay_response(self, row, leave=None):
        data = fields(
            row,
            "id room_id bed_id student_id student_name student_reference hostel_name room_number bed_label monthly_fee allocated_date_ad vacated_date_ad academic_year_bs notes checkout_reason previous_allocation_id",
        )
        data.update(
            status=row.status.value,
            allocated_date_bs=NepalCalendar.ad_to_bs(row.allocated_date_ad),
            vacated_date_bs=NepalCalendar.ad_to_bs(row.vacated_date_ad)
            if row.vacated_date_ad
            else None,
            leave_id=str(leave.id) if leave else None,
            expected_return_ad=leave.expected_return_ad.isoformat() if leave else None,
            expected_return_bs=NepalCalendar.ad_to_bs(leave.expected_return_ad)
            if leave
            else None,
            return_overdue=bool(leave and leave.expected_return_ad < today()),
        )
        return data

    async def _sync(self, school, room):
        await self.db.flush()
        room.capacity = await self.db.scalar(
            select(func.count())
            .select_from(HostelBed)
            .where(
                HostelBed.school_id == school,
                HostelBed.room_id == room.id,
                HostelBed.status != "retired",
            )
        )
        room.occupied = await self.db.scalar(
            select(func.count())
            .select_from(RoomAllocation)
            .where(
                RoomAllocation.school_id == school,
                RoomAllocation.room_id == room.id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
        )
        await self.db.flush()
        hostel = await self.get(Hostel, school, room.hostel_id)
        hostel.total_rooms, hostel.capacity = (
            await self.db.execute(
                select(func.count(), func.coalesce(func.sum(Room.capacity), 0)).where(
                    Room.school_id == school,
                    Room.hostel_id == hostel.id,
                    Room.is_active.is_(True),
                )
            )
        ).one()
        await self.db.flush()

    async def _create_hostel(self, school, data, resource, actor):
        hostel = Hostel(
            id=uuid4(),
            school_id=school,
            total_rooms=0,
            capacity=0,
            is_active=True,
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(hostel)
        await self.db.flush()
        return self.hostel_response(hostel)

    async def _update_hostel(self, school, data, resource, actor):
        hostel = await self.get(Hostel, school, resource, True)
        occupied = await self.db.scalar(
            select(func.count())
            .select_from(RoomAllocation)
            .join(Room, Room.id == RoomAllocation.room_id)
            .where(
                RoomAllocation.school_id == school,
                Room.hostel_id == hostel.id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
        )
        if occupied and (not data.is_active or data.hostel_type != hostel.hostel_type):
            raise HostelConflict(
                "Transfer or check out all residents before archiving or changing hostel type"
            )
        self.before = self.hostel_response(hostel)
        for name, value in data.model_dump(exclude={"request_id"}).items():
            setattr(hostel, name, value)
        await self.db.flush()
        return self.hostel_response(hostel)

    async def _new_beds(self, school, room, count, labels=None, notes=None):
        existing = set(
            (
                await self.db.scalars(
                    select(HostelBed.label).where(
                        HostelBed.school_id == school, HostelBed.room_id == room.id
                    )
                )
            ).all()
        )
        if room.capacity + count > 500:
            raise ValueError(
                "A room can have at most 500 registered beds; create another room for larger capacity"
            )
        if labels is None:
            labels, number = [], len(existing) + 1
            while len(labels) < count:
                candidate = f"B-{number:04d}"
                if candidate not in existing:
                    labels.append(candidate)
                number += 1
        if set(labels) & existing:
            raise HostelConflict(
                "A bed label already exists in this room, including retired beds"
            )
        self.db.add_all(
            [
                HostelBed(
                    id=uuid4(),
                    school_id=school,
                    room_id=room.id,
                    label=label,
                    status="active",
                    notes=notes,
                )
                for label in labels
            ]
        )
        await self._sync(school, room)
        return labels

    async def _create_room(self, school, data, resource, actor):
        hostel = await self.get(Hostel, school, data.hostel_id, True)
        if not hostel.is_active:
            raise HostelConflict("Restore the hostel before adding rooms")
        room = Room(
            id=uuid4(),
            school_id=school,
            capacity=0,
            occupied=0,
            is_active=True,
            **data.model_dump(exclude={"request_id", "capacity"}),
        )
        self.db.add(room)
        await self.db.flush()
        await self._new_beds(school, room, data.capacity)
        return self.room_response(room)

    async def _update_room(self, school, data, resource, actor):
        room = await self.get(Room, school, resource, True)
        hostel = await self.get(Hostel, school, room.hostel_id)
        if data.is_active and not hostel.is_active:
            raise HostelConflict("Restore the hostel before activating this room")
        if room.occupied and not data.is_active:
            raise HostelConflict(
                "Transfer or check out residents before archiving a room"
            )
        self.before = self.room_response(room)
        for name, value in data.model_dump(exclude={"request_id"}).items():
            setattr(room, name, value)
        await self._sync(school, room)
        return self.room_response(room)

    async def _add_beds(self, school, data, resource, actor):
        room = await self.get(Room, school, resource, True)
        labels = await self._new_beds(school, room, data.count, data.labels, data.notes)
        return self.room_response(room) | {"beds_added": labels}

    async def _update_bed(self, school, data, resource, actor):
        bed = await self.get(HostelBed, school, resource, True)
        if await self.db.scalar(
            select(RoomAllocation.id).where(
                RoomAllocation.school_id == school,
                RoomAllocation.bed_id == bed.id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
        ):
            raise HostelConflict(
                "Transfer or check out the resident before blocking or retiring this bed"
            )
        room = await self.get(Room, school, bed.room_id, True)
        if (
            bed.status == "retired"
            and data.status != "retired"
            and room.capacity >= 500
        ):
            raise HostelConflict("This room has reached the 500-bed limit")
        self.before = fields(bed, "status notes label")
        bed.status, bed.notes = data.status, data.notes
        await self._sync(school, room)
        return fields(bed, "id room_id label status notes")

    async def _student(self, school, student_id, lock=False, eligible=True):
        student = await self.get(Student, school, student_id, lock)
        if eligible and (
            student.status != StudentStatus.ACTIVE
            or student.is_deleted
            or student.deleted_at is not None
        ):
            raise HostelConflict(
                "New stays and transfers require an active student enrolled in this school"
            )
        return student

    async def _admit(
        self, school, room_id, bed_id, student_id, year, notes, previous=None
    ):
        student = await self._student(school, student_id, True)
        room = await self.get(Room, school, room_id, True)
        hostel = await self.get(Hostel, school, room.hostel_id)
        if not room.is_active or not hostel.is_active:
            raise HostelConflict("Choose an active hostel and room")
        if (
            hostel.hostel_type == HostelType.BOYS
            and student.gender != Gender.MALE
            or hostel.hostel_type == HostelType.GIRLS
            and student.gender != Gender.FEMALE
        ):
            raise HostelConflict(
                "The student does not match this hostel type; select an appropriate hostel"
            )
        if await self.db.scalar(
            select(RoomAllocation.id).where(
                RoomAllocation.school_id == school,
                RoomAllocation.student_id == student_id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
        ):
            raise HostelConflict("This student already has an active hostel stay")
        occupied = (
            select(RoomAllocation.id)
            .where(
                RoomAllocation.school_id == school,
                RoomAllocation.bed_id == HostelBed.id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
            .exists()
        )
        query = select(HostelBed).where(
            HostelBed.school_id == school,
            HostelBed.room_id == room.id,
            HostelBed.status == "active",
            ~occupied,
        )
        if bed_id:
            query = query.where(HostelBed.id == bed_id)
        bed = await self.db.scalar(
            query.order_by(HostelBed.label, HostelBed.id).limit(1).with_for_update()
        )
        if bed is None:
            raise HostelConflict("No available bed matches this selection")
        current_year = normalize_academic_year(NepalCalendar.ad_to_bs(today())[:4])
        if year and year != current_year:
            raise ValueError(
                f"New admissions must use the current BS academic year, {current_year}"
            )
        stay = RoomAllocation(
            id=uuid4(),
            school_id=school,
            student_id=student.id,
            room_id=room.id,
            bed_id=bed.id,
            student_name=student.full_name_en,
            student_reference=student.admission_number
            or student.emis_student_id
            or f'Grade {student.current_grade or "—"} {student.current_section or ""} · Roll {student.roll_number or "—"}',
            hostel_name=hostel.name,
            room_number=room.room_number,
            bed_label=bed.label,
            monthly_fee=room.monthly_fee,
            allocated_date_ad=today(),
            created_at=datetime.now(NPT),
            status=AllocationStatus.ACTIVE,
            academic_year_bs=year or current_year,
            notes=notes,
            previous_allocation_id=previous,
        )
        self.db.add(stay)
        await self._sync(school, room)
        self.stay_id = stay.id
        return stay

    async def _allocate(self, school, data, resource, actor):
        return self.stay_response(
            await self._admit(
                school,
                data.room_id,
                data.bed_id,
                data.student_id,
                data.academic_year_bs,
                data.notes,
            )
        )

    async def _active_stay(self, school, resource):
        stay = await self.get(RoomAllocation, school, resource, True)
        self.stay_id = stay.id
        if stay.status != AllocationStatus.ACTIVE:
            raise HostelConflict(
                "This stay has already been checked out or transferred"
            )
        return stay

    async def _can_close(self, school, stay):
        if await self.db.scalar(
            select(HostelLeave.id).where(
                HostelLeave.school_id == school,
                HostelLeave.allocation_id == stay.id,
                HostelLeave.returned_at.is_(None),
            )
        ):
            raise HostelConflict(
                "Record the return from leave before checkout or transfer"
            )
        if await self.db.scalar(
            select(HostelVisit.id).where(
                HostelVisit.school_id == school,
                HostelVisit.allocation_id == stay.id,
                HostelVisit.departed_at.is_(None),
            )
        ):
            raise HostelConflict("Check out open visitors before checkout or transfer")

    async def _close(self, school, stay, reason):
        self.before = self.stay_response(stay)
        stay.status, stay.vacated_date_ad, stay.checkout_reason = (
            AllocationStatus.VACATED,
            today(),
            reason,
        )
        await self._sync(school, await self.get(Room, school, stay.room_id, True))

    async def _vacate(self, school, data, resource, actor):
        stay = await self._active_stay(school, resource)
        await self._can_close(school, stay)
        await self._close(school, stay, data.notes)
        return self.stay_response(stay)

    async def _transfer(self, school, data, resource, actor):
        stay = await self._active_stay(school, resource)
        await self._can_close(school, stay)
        if data.room_id == stay.room_id and (
            data.bed_id is None or data.bed_id == stay.bed_id
        ):
            raise HostelConflict("Select a different room or bed for transfer")
        await self._close(school, stay, data.notes)
        new_stay = await self._admit(
            school,
            data.room_id,
            data.bed_id,
            stay.student_id,
            None,
            data.notes,
            stay.id,
        )
        return self.stay_response(new_stay)

    def leave_response(self, leave):
        return fields(
            leave,
            "id allocation_id departed_at expected_return_ad returned_at destination responsible_person contact_phone reason return_notes",
        ) | {
            "expected_return_bs": NepalCalendar.ad_to_bs(leave.expected_return_ad),
            "overdue": leave.returned_at is None and leave.expected_return_ad < today(),
        }

    async def _leave(self, school, data, resource, actor):
        stay = await self._active_stay(school, resource)
        if not today() <= data.expected_return_ad <= today() + timedelta(days=365):
            raise ValueError(
                "Expected return must be today or within the next 365 days"
            )
        if await self.db.scalar(
            select(HostelLeave.id).where(
                HostelLeave.school_id == school,
                HostelLeave.allocation_id == stay.id,
                HostelLeave.returned_at.is_(None),
            )
        ):
            raise HostelConflict("The resident is already recorded as away on leave")
        leave = HostelLeave(
            id=uuid4(),
            school_id=school,
            allocation_id=stay.id,
            departed_at=datetime.now(NPT),
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(leave)
        await self.db.flush()
        return self.leave_response(leave)

    async def _return_leave(self, school, data, resource, actor):
        leave = await self.get(HostelLeave, school, resource, True)
        self.stay_id = leave.allocation_id
        if leave.returned_at:
            raise HostelConflict("The return from leave was already recorded")
        leave.returned_at, leave.return_notes = datetime.now(NPT), data.notes
        await self.db.flush()
        return self.leave_response(leave)

    async def _visit(self, school, data, resource, actor):
        stay = await self._active_stay(school, data.allocation_id)
        visit = HostelVisit(
            id=uuid4(),
            school_id=school,
            arrived_at=datetime.now(NPT),
            **data.model_dump(exclude={"request_id"}),
        )
        self.db.add(visit)
        await self.db.flush()
        return fields(
            visit,
            "id allocation_id visitor_name relation contact_phone purpose arrived_at departed_at",
        ) | {"student_name": stay.student_name}

    async def _depart_visit(self, school, data, resource, actor):
        visit = await self.get(HostelVisit, school, resource, True)
        self.stay_id = visit.allocation_id
        if visit.departed_at:
            raise HostelConflict("This visitor has already checked out")
        visit.departed_at = datetime.now(NPT)
        await self.db.flush()
        return fields(
            visit,
            "id allocation_id visitor_name relation contact_phone purpose arrived_at departed_at",
        )

    def stays_query(
        self,
        school,
        hostel_id=None,
        room_id=None,
        status=None,
        search=None,
        on_date=None,
    ):
        query = (
            select(RoomAllocation)
            .join(Room, Room.id == RoomAllocation.room_id)
            .where(RoomAllocation.school_id == school, Room.school_id == school)
        )
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        if room_id:
            query = query.where(RoomAllocation.room_id == room_id)
        if on_date:
            query = query.where(
                RoomAllocation.allocated_date_ad <= on_date,
                or_(
                    RoomAllocation.vacated_date_ad.is_(None),
                    RoomAllocation.vacated_date_ad >= on_date,
                ),
            )
            # A same-day transfer belongs to the final bed on that day. Existing
            # saved marks for earlier stays remain available in history/export.
            from sqlalchemy.orm import aliased

            following = aliased(RoomAllocation)
            later = or_(
                following.allocated_date_ad > RoomAllocation.allocated_date_ad,
                (following.allocated_date_ad == RoomAllocation.allocated_date_ad)
                & (following.created_at > RoomAllocation.created_at),
                (following.allocated_date_ad == RoomAllocation.allocated_date_ad)
                & (following.created_at == RoomAllocation.created_at)
                & (following.id > RoomAllocation.id),
            )
            query = query.where(
                ~select(following.id)
                .where(
                    following.school_id == school,
                    following.student_id == RoomAllocation.student_id,
                    following.allocated_date_ad <= on_date,
                    or_(
                        following.vacated_date_ad.is_(None),
                        following.vacated_date_ad >= on_date,
                    ),
                    later,
                )
                .exists()
            )
        elif status in ("active", "vacated"):
            query = query.where(RoomAllocation.status == AllocationStatus(status))
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    RoomAllocation.student_name.ilike(pattern),
                    RoomAllocation.student_reference.ilike(pattern),
                    RoomAllocation.hostel_name.ilike(pattern),
                    RoomAllocation.room_number.ilike(pattern),
                    RoomAllocation.bed_label.ilike(pattern),
                )
            )
        return query.order_by(
            RoomAllocation.allocated_date_ad.desc(),
            RoomAllocation.student_name,
            RoomAllocation.id,
        )

    async def page(self, query, page=1, limit=20):
        total = await self.db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        rows = (
            await self.db.scalars(query.offset((page - 1) * limit).limit(limit))
        ).all()
        return rows, total

    async def list_hostels(self, school, page=1, search=None, is_active=True):
        query = select(Hostel).where(
            Hostel.school_id == school, Hostel.is_active == is_active
        )
        if search:
            query = query.where(Hostel.name.ilike(f"%{search}%"))
        rows, total = await self.page(query.order_by(Hostel.name, Hostel.id), page)
        return {"hostels": [self.hostel_response(row) for row in rows], "total": total}

    def rooms_query(
        self, school, hostel_id=None, search=None, is_active=True, available_only=False
    ):
        query = (
            select(Room)
            .join(Hostel, Hostel.id == Room.hostel_id)
            .where(
                Room.school_id == school,
                Hostel.school_id == school,
                Room.is_active == is_active,
            )
        )
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        if search:
            query = query.where(
                or_(
                    Room.room_number.ilike(f"%{search}%"),
                    Hostel.name.ilike(f"%{search}%"),
                )
            )
        if available_only:
            occupied = (
                select(RoomAllocation.id)
                .where(
                    RoomAllocation.school_id == school,
                    RoomAllocation.bed_id == HostelBed.id,
                    RoomAllocation.status == AllocationStatus.ACTIVE,
                )
                .exists()
            )
            query = query.where(
                Hostel.is_active.is_(True),
                select(HostelBed.id)
                .where(
                    HostelBed.school_id == school,
                    HostelBed.room_id == Room.id,
                    HostelBed.status == "active",
                    ~occupied,
                )
                .exists(),
            )
        return query.order_by(Hostel.name, Room.floor, Room.room_number, Room.id)

    async def list_rooms(self, school, page=1, **filters):
        rows, total = await self.page(self.rooms_query(school, **filters), page)
        ids = [row.id for row in rows]
        used = (
            select(RoomAllocation.id)
            .where(
                RoomAllocation.school_id == school,
                RoomAllocation.bed_id == HostelBed.id,
                RoomAllocation.status == AllocationStatus.ACTIVE,
            )
            .exists()
        )
        available = (
            dict(
                (
                    await self.db.execute(
                        select(HostelBed.room_id, func.count())
                        .where(
                            HostelBed.school_id == school,
                            HostelBed.room_id.in_(ids),
                            HostelBed.status == "active",
                            ~used,
                        )
                        .group_by(HostelBed.room_id)
                    )
                ).all()
            )
            if ids
            else {}
        )
        hostels = (
            {
                row.id: row
                for row in (
                    await self.db.scalars(
                        select(Hostel).where(
                            Hostel.school_id == school,
                            Hostel.id.in_({row.hostel_id for row in rows}),
                        )
                    )
                ).all()
            }
            if ids
            else {}
        )
        return {
            "rooms": [
                self.room_response(row)
                | {
                    "hostel_name": hostels[row.hostel_id].name,
                    "hostel_type": hostels[row.hostel_id].hostel_type.value,
                    "hostel_active": hostels[row.hostel_id].is_active,
                    "available_beds": available.get(row.id, 0)
                    if row.is_active and hostels[row.hostel_id].is_active
                    else 0,
                }
                for row in rows
            ],
            "total": total,
        }

    async def beds(self, school, room_id, page=1):
        room = await self.get(Room, school, room_id)
        rows, total = await self.page(
            select(HostelBed)
            .where(HostelBed.school_id == school, HostelBed.room_id == room_id)
            .order_by(HostelBed.label, HostelBed.id),
            page,
        )
        stays = (
            (
                await self.db.scalars(
                    select(RoomAllocation).where(
                        RoomAllocation.school_id == school,
                        RoomAllocation.bed_id.in_([row.id for row in rows]),
                        RoomAllocation.status == AllocationStatus.ACTIVE,
                    )
                )
            ).all()
            if rows
            else []
        )
        by_bed = {stay.bed_id: self.stay_response(stay) for stay in stays}
        hostel = await self.get(Hostel, school, room.hostel_id)
        return {
            "room": self.room_response(room),
            "hostel": self.hostel_response(hostel),
            "beds": [
                fields(row, "id room_id label status notes")
                | {"resident": by_bed.get(row.id)}
                for row in rows
            ],
            "total": total,
        }

    async def residents(self, school, page=1, **filters):
        rows, total = await self.page(self.stays_query(school, **filters), page)
        leaves = (
            (
                await self.db.scalars(
                    select(HostelLeave).where(
                        HostelLeave.school_id == school,
                        HostelLeave.allocation_id.in_([row.id for row in rows]),
                        HostelLeave.returned_at.is_(None),
                    )
                )
            ).all()
            if rows
            else []
        )
        by_stay = {row.allocation_id: row for row in leaves}
        return {
            "residents": [self.stay_response(row, by_stay.get(row.id)) for row in rows],
            "total": total,
        }

    async def students(self, school, search=None, page=1):
        query = select(
            Student.id,
            Student.full_name_en,
            Student.full_name_np,
            Student.admission_number,
            Student.emis_student_id,
            Student.current_grade,
            Student.current_section,
            Student.roll_number,
            Student.gender,
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
        stays = (
            dict(
                (
                    await self.db.execute(
                        select(RoomAllocation.student_id, RoomAllocation.id).where(
                            RoomAllocation.school_id == school,
                            RoomAllocation.student_id.in_([row.id for row in rows]),
                            RoomAllocation.status == AllocationStatus.ACTIVE,
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
                    "active_allocation_id": str(stays[row.id])
                    if row.id in stays
                    else None
                }
                for row in rows
            ],
            "total": total,
        }

    async def movements(
        self,
        school,
        kind,
        page=1,
        hostel_id=None,
        search=None,
        status="open",
        allocation_id=None,
    ):
        model = HostelLeave if kind == "leaves" else HostelVisit
        query = (
            select(model)
            .join(RoomAllocation, RoomAllocation.id == model.allocation_id)
            .join(Room, Room.id == RoomAllocation.room_id)
            .where(
                model.school_id == school,
                RoomAllocation.school_id == school,
                Room.school_id == school,
            )
        )
        closed = model.returned_at if kind == "leaves" else model.departed_at
        if status == "open":
            query = query.where(closed.is_(None))
        elif status == "closed":
            query = query.where(closed.is_not(None))
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        if allocation_id:
            query = query.where(model.allocation_id == allocation_id)
        if search:
            clauses = [RoomAllocation.student_name.ilike(f"%{search}%")]
            if kind == "visits":
                clauses.append(HostelVisit.visitor_name.ilike(f"%{search}%"))
            query = query.where(or_(*clauses))
        rows, total = await self.page(
            query.order_by(model.created_at.desc(), model.id), page
        )
        stays = (
            {
                row.id: row
                for row in (
                    await self.db.scalars(
                        select(RoomAllocation).where(
                            RoomAllocation.school_id == school,
                            RoomAllocation.id.in_([row.allocation_id for row in rows]),
                        )
                    )
                ).all()
            }
            if rows
            else {}
        )
        return {
            "records": [
                (
                    self.leave_response(row)
                    if kind == "leaves"
                    else fields(
                        row,
                        "id allocation_id visitor_name relation contact_phone purpose arrived_at departed_at",
                    )
                )
                | {
                    "student_name": stays[row.allocation_id].student_name,
                    "hostel_name": stays[row.allocation_id].hostel_name,
                    "room_number": stays[row.allocation_id].room_number,
                }
                for row in rows
            ],
            "total": total,
        }

    def validate_register_date(self, day):
        NepalCalendar.ad_to_bs(day)
        if day > today():
            raise ValueError(
                "Attendance and meal records cannot be entered for a future date"
            )

    async def register(self, school, day, session, page=1, hostel_id=None, search=None):
        self.validate_register_date(day)
        rows, total = await self.page(
            self.stays_query(school, hostel_id=hostel_id, search=search, on_date=day),
            page,
        )
        ids = [row.id for row in rows]
        marks = (
            (
                await self.db.scalars(
                    select(HostelRegister).where(
                        HostelRegister.school_id == school,
                        HostelRegister.date_ad == day,
                        HostelRegister.session == session,
                        HostelRegister.allocation_id.in_(ids),
                    )
                )
            ).all()
            if ids
            else []
        )
        by_stay = {row.allocation_id: row for row in marks}
        return {
            "date_ad": day.isoformat(),
            "date_bs": NepalCalendar.ad_to_bs(day),
            "session": session,
            "total": total,
            "entries": [
                self.stay_response(row)
                | {
                    "recorded_status": by_stay[row.id].status
                    if row.id in by_stay
                    else None,
                    "recorded_notes": by_stay[row.id].notes
                    if row.id in by_stay
                    else None,
                    "version": by_stay[row.id].version if row.id in by_stay else 0,
                }
                for row in rows
            ],
        }

    async def _save_register(self, school, data, resource, actor):
        self.validate_register_date(data.date_ad)
        ids = [entry.allocation_id for entry in data.entries]
        valid = set(
            (
                await self.db.scalars(
                    self.stays_query(school, on_date=data.date_ad).where(
                        RoomAllocation.id.in_(ids)
                    )
                )
            ).all()
        )
        if {row.id for row in valid} != set(ids):
            raise HostelConflict(
                "A selected stay does not belong to this date or school; reload the register"
            )
        existing = (
            await self.db.scalars(
                select(HostelRegister)
                .where(
                    HostelRegister.school_id == school,
                    HostelRegister.allocation_id.in_(ids),
                    HostelRegister.date_ad == data.date_ad,
                    HostelRegister.session == data.session,
                )
                .with_for_update()
            )
        ).all()
        by_stay = {row.allocation_id: row for row in existing}
        for entry in data.entries:
            mark = by_stay.get(entry.allocation_id)
            if entry.version != (mark.version if mark else 0):
                raise HostelConflict(
                    "Another staff member updated this register. Reload before saving your changes"
                )
            if entry.status in ("absent", "excused") and (
                not entry.notes or len(entry.notes) < 3
            ):
                raise ValueError(
                    "Add a reason or follow-up note for absent and excused residents"
                )
        self.before = {
            "entries": [
                fields(row, "allocation_id status notes version") for row in existing
            ]
        }
        for entry in data.entries:
            mark = by_stay.get(entry.allocation_id)
            if mark is None:
                mark = HostelRegister(
                    id=uuid4(),
                    school_id=school,
                    allocation_id=entry.allocation_id,
                    date_ad=data.date_ad,
                    session=data.session,
                    version=0,
                )
                self.db.add(mark)
            mark.status, mark.notes, mark.recorded_by, mark.version = (
                entry.status,
                entry.notes,
                actor,
                mark.version + 1,
            )
        await self.db.flush()
        return {
            "saved": len(data.entries),
            "date_ad": data.date_ad.isoformat(),
            "date_bs": NepalCalendar.ad_to_bs(data.date_ad),
            "session": data.session,
        }

    async def fee_options(self, school, stay_id, month):
        stay = await self.get(RoomAllocation, school, stay_id)
        student = await self._student(school, stay.student_id, eligible=False)
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
            "monthly_fee": str(stay.monthly_fee),
            "options": [
                {key: json_value(value) for key, value in row._mapping.items()}
                for row in rows
            ],
        }

    async def _bill(self, school, data, resource, actor):
        stay = await self.get(RoomAllocation, school, resource)
        self.stay_id = stay.id
        start = NepalCalendar.bs_to_ad(f"{data.month_bs}-01")
        year, month = map(int, data.month_bs.split("-"))
        end = NepalCalendar.bs_to_ad(
            f"{year+1 if month==12 else year}-{1 if month==12 else month+1:02d}-01"
        ) - timedelta(days=1)
        if (
            stay.allocated_date_ad > end
            or stay.vacated_date_ad
            and stay.vacated_date_ad < start
        ):
            raise ValueError(
                "The resident did not stay in this room during the selected BS month"
            )
        if start > today():
            raise ValueError(
                "Generate hostel bills for the current or an earlier BS month"
            )
        head = await self.db.scalar(
            select(FeeHead)
            .join(FeeStructure, FeeStructure.id == FeeHead.fee_structure_id)
            .where(FeeHead.id == data.fee_head_id, FeeStructure.school_id == school)
        )
        if head is None:
            raise RecordNotFoundError("FeeHead", str(data.fee_head_id))
        structure = await self.get(FeeStructure, school, head.fee_structure_id, True)
        student = await self._student(school, stay.student_id, True, eligible=False)
        await self.db.refresh(head)
        if (
            not structure.is_active
            or structure.grade != str(student.current_grade)
            or structure.academic_year_bs != normalize_academic_year(str(year))
        ):
            raise ValueError(
                "Choose an active fee structure for this student grade and BS year"
            )
        if (
            not head.is_optional
            or head.frequency != FeeFrequency.monthly
            or head.amount != stay.monthly_fee
            or stay.monthly_fee <= 0
        ):
            raise ValueError(
                "Select an optional monthly hostel fee head matching this stay’s agreed monthly charge"
            )
        charge = await self.db.scalar(
            select(HostelCharge).where(
                HostelCharge.school_id == school,
                HostelCharge.student_id == stay.student_id,
                HostelCharge.month_bs == data.month_bs,
            )
        )
        if charge:
            ledger = await self.get(FeeLedger, school, charge.ledger_id)
            if (
                ledger.fee_head_id != head.id
                or ledger.original_amount != stay.monthly_fee
            ):
                raise HostelConflict(
                    "This student already has a hostel bill for this BS month; review it in Fees & Payments"
                )
            return {
                "ledger_id": str(ledger.id),
                "student_name": stay.student_name,
                "month_bs": data.month_bs,
                "amount": str(ledger.original_amount),
                "already_billed": True,
            }
        due = NepalCalendar.bs_to_ad(f"{data.month_bs}-{data.due_day_bs:02d}")
        result = await self.db.execute(
            pg_insert(FeeLedger)
            .values(
                id=uuid4(),
                school_id=school,
                student_id=stay.student_id,
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
        ledger_id = result.scalar_one_or_none()
        already = ledger_id is None
        if already:
            ledger = await self.db.scalar(
                select(FeeLedger).where(
                    FeeLedger.school_id == school,
                    FeeLedger.student_id == stay.student_id,
                    FeeLedger.fee_head_id == head.id,
                    FeeLedger.academic_year_bs == structure.academic_year_bs,
                    FeeLedger.month_bs == data.month_bs,
                )
            )
            if ledger.original_amount != stay.monthly_fee:
                raise HostelConflict(
                    "An existing bill has different original charges; review it in Fees & Payments"
                )
            ledger_id = ledger.id
        self.db.add(
            HostelCharge(
                id=uuid4(),
                school_id=school,
                allocation_id=stay.id,
                student_id=stay.student_id,
                month_bs=data.month_bs,
                ledger_id=ledger_id,
            )
        )
        await self.db.flush()
        return {
            "ledger_id": str(ledger_id),
            "student_name": stay.student_name,
            "month_bs": data.month_bs,
            "amount": str(head.amount),
            "already_billed": already,
        }

    async def occupancy(self, school, hostel_id=None):
        query = (
            select(Room)
            .join(Hostel, Hostel.id == Room.hostel_id)
            .where(
                Room.school_id == school,
                Hostel.school_id == school,
                Room.is_active.is_(True),
                Hostel.is_active.is_(True),
            )
        )
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        room_ids = query.with_only_columns(Room.id).order_by(None)
        capacity, occupied = (
            await self.db.execute(
                select(
                    func.count().filter(HostelBed.status == "active"),
                    func.count().filter(HostelBed.status == "maintenance"),
                ).where(HostelBed.school_id == school, HostelBed.room_id.in_(room_ids))
            )
        ).one()
        residents = await self.db.scalar(
            select(func.count())
            .select_from(RoomAllocation)
            .where(
                RoomAllocation.school_id == school,
                RoomAllocation.status == AllocationStatus.ACTIVE,
                RoomAllocation.room_id.in_(room_ids),
            )
        )
        leaves, overdue = (
            await self.db.execute(
                select(
                    func.count(),
                    func.count().filter(HostelLeave.expected_return_ad < today()),
                )
                .join(RoomAllocation, RoomAllocation.id == HostelLeave.allocation_id)
                .where(
                    HostelLeave.school_id == school,
                    HostelLeave.returned_at.is_(None),
                    RoomAllocation.school_id == school,
                    RoomAllocation.room_id.in_(room_ids),
                )
            )
        ).one()
        return {
            "total_hostels": await self.db.scalar(
                select(func.count())
                .select_from(Hostel)
                .where(
                    Hostel.school_id == school,
                    Hostel.is_active.is_(True),
                    Hostel.id == hostel_id if hostel_id else True,
                )
            ),
            "total_rooms": await self.db.scalar(
                select(func.count()).select_from(query.subquery())
            ),
            "total_capacity": capacity,
            "maintenance_beds": occupied,
            "total_occupied": residents,
            "available_beds": max(0, capacity - residents),
            "on_leave": leaves,
            "overdue_returns": overdue,
            "occupancy_rate": round(residents / capacity * 100, 1) if capacity else 0,
        }

    async def history(self, school, page=1, allocation_id=None):
        query = select(HostelEvent).where(HostelEvent.school_id == school)
        if allocation_id:
            await self.get(RoomAllocation, school, allocation_id)
            query = query.where(
                or_(
                    HostelEvent.allocation_id == allocation_id,
                    (HostelEvent.action == "transfer")
                    & (HostelEvent.payload["resource_id"].astext == str(allocation_id)),
                    (HostelEvent.action == "save_register")
                    & HostelEvent.payload["entries"].contains(
                        [{"allocation_id": str(allocation_id)}]
                    ),
                )
            )
        rows, total = await self.page(
            query.order_by(HostelEvent.created_at.desc(), HostelEvent.id), page
        )
        register_ids = {
            UUID(entry["allocation_id"])
            for row in rows
            if row.action == "save_register"
            for entry in row.payload["entries"]
        }
        names = (
            dict(
                (
                    await self.db.execute(
                        select(RoomAllocation.id, RoomAllocation.student_name).where(
                            RoomAllocation.school_id == school,
                            RoomAllocation.id.in_(register_ids),
                        )
                    )
                ).all()
            )
            if register_ids
            else {}
        )

        def changes(row):
            if row.action != "save_register":
                return []
            previous = {
                entry["allocation_id"]: entry
                for entry in row.before_values.get("entries", [])
            }
            return [
                {
                    "student_name": names.get(UUID(entry["allocation_id"]), "Resident"),
                    "status": entry["status"],
                    "notes": entry.get("notes"),
                    "previous_status": previous.get(entry["allocation_id"], {}).get(
                        "status"
                    ),
                }
                for entry in row.payload["entries"]
                if not allocation_id or entry["allocation_id"] == str(allocation_id)
            ]

        return {
            "events": [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "actor_name": row.actor_name,
                    "created_at": row.created_at.isoformat(),
                    "label": row.result.get("student_name")
                    or row.result.get("name")
                    or row.result.get("room_number")
                    or row.result.get("visitor_name"),
                    "notes": row.payload.get("notes")
                    or row.payload.get("reason")
                    or row.payload.get("purpose"),
                    "before": row.before_values
                    if row.action not in ("save_register",)
                    else {},
                    "after": {
                        key: value
                        for key, value in row.result.items()
                        if key
                        in (
                            "room_number",
                            "name",
                            "hostel_type",
                            "is_active",
                            "capacity",
                            "status",
                            "monthly_fee",
                            "beds_added",
                            "date_bs",
                            "session",
                            "saved",
                        )
                    },
                    "register_changes": changes(row),
                }
                for row in rows
            ],
            "total": total,
        }

    async def export(
        self,
        school,
        report,
        hostel_id=None,
        search=None,
        status=None,
        day=None,
        session="evening",
    ):
        if report == "residents":
            rows = (
                await self.db.scalars(
                    self.stays_query(
                        school, hostel_id=hostel_id, search=search, status=status
                    ).limit(50_001)
                )
            ).all()
            header = [
                "Student",
                "Reference",
                "Hostel",
                "Room",
                "Bed",
                "Admitted BS",
                "Admitted AD",
                "Vacated AD",
                "Status",
                "Agreed monthly charge NPR",
            ]
            values = [
                (
                    r.student_name,
                    r.student_reference,
                    r.hostel_name,
                    r.room_number,
                    r.bed_label,
                    NepalCalendar.ad_to_bs(r.allocated_date_ad),
                    r.allocated_date_ad,
                    r.vacated_date_ad,
                    r.status.value,
                    r.monthly_fee,
                )
                for r in rows
            ]
        else:
            self.validate_register_date(day or today())
            query = (
                select(HostelRegister, RoomAllocation)
                .join(RoomAllocation, RoomAllocation.id == HostelRegister.allocation_id)
                .join(Room, Room.id == RoomAllocation.room_id)
                .where(
                    HostelRegister.school_id == school,
                    RoomAllocation.school_id == school,
                    Room.school_id == school,
                    HostelRegister.date_ad == (day or today()),
                    HostelRegister.session == session,
                    Room.hostel_id == hostel_id if hostel_id else True,
                )
            )
            if search:
                pattern = f"%{search}%"
                query = query.where(
                    or_(
                        RoomAllocation.student_name.ilike(pattern),
                        RoomAllocation.student_reference.ilike(pattern),
                        RoomAllocation.hostel_name.ilike(pattern),
                        RoomAllocation.room_number.ilike(pattern),
                        RoomAllocation.bed_label.ilike(pattern),
                    )
                )
            rows = (
                await self.db.execute(
                    query.order_by(
                        RoomAllocation.student_name, RoomAllocation.id
                    ).limit(50_001)
                )
            ).all()
            header = [
                "Student",
                "Hostel",
                "Room",
                "Bed",
                "Date BS",
                "Date AD",
                "Session",
                "Status",
                "Notes",
            ]
            values = [
                (
                    r.student_name,
                    r.hostel_name,
                    r.room_number,
                    r.bed_label,
                    NepalCalendar.ad_to_bs(mark.date_ad),
                    mark.date_ad,
                    mark.session,
                    mark.status,
                    mark.notes,
                )
                for mark, r in rows
            ]
        if len(rows) > 50_000:
            raise ValueError("Narrow the filters to export at most 50,000 records")
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
