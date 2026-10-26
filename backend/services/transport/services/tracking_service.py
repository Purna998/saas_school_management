"""Phone-scoped writes, bounded latest fixes and private family journey views."""

import hashlib
import math
import secrets
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload
from services.auth.models.user import User, UserStatus
from services.auth.models.role import Role
from services.student.models.student import Student, StudentStatus
from services.transport.models.transport import (
    TransportFamilyAccess,
    TransportPhoneSession,
    TransportLivePosition,
    TransportTrip,
    TransportPassenger,
    TransportEvent,
)
from services.transport.services.transport_service import (
    TransportService,
    TransportConflict,
    now,
    today,
)
from shared.utils.nepali_calendar import NepalCalendar


def staff_view(user):
    if user.has_role("parent") or user.has_role("student"):
        return user.has_permission("transport:create") and user.has_permission(
            "transport:read"
        )
    return user.has_permission("transport:track") or user.has_permission(
        "transport:read"
    )


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(float(lat1)), math.radians(float(lat2))
    dlat, dlon = b - a, math.radians(float(lon2) - float(lon1))
    hav = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return round(6371000 * 2 * math.asin(min(1, math.sqrt(hav))))


class TrackingService(TransportService):
    async def _link_parent(self, school, data, resource):
        student = await self.get(Student, school, data.student_id)
        if (
            student.deleted_at
            or student.is_deleted
            or student.status != StudentStatus.ACTIVE
        ):
            raise ValueError("Choose a current enrolled student")
        parent = await self.db.scalar(
            select(User)
            .where(
                User.school_id == school,
                func.lower(User.email) == str(data.parent_email).lower(),
                User.status == UserStatus.ACTIVE,
            )
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        if not parent or not parent.has_role("parent"):
            raise ValueError(
                "Choose an active parent account in this school; the office must verify the relationship"
            )
        row = await self.db.scalar(
            select(TransportFamilyAccess).where(
                TransportFamilyAccess.school_id == school,
                TransportFamilyAccess.student_id == student.id,
                TransportFamilyAccess.parent_id == parent.id,
                TransportFamilyAccess.revoked_at.is_(None),
            )
        )
        if row:
            raise TransportConflict(
                "This parent already has access to this student's journeys"
            )
        # command() supplies the audited actor; use it rather than a client actor ID.
        row = TransportFamilyAccess(
            id=uuid4(),
            school_id=school,
            student_id=student.id,
            parent_id=parent.id,
            created_by=self.actor_id,
            notes=data.notes,
        )
        self.db.add(row)
        await self.db.flush()
        return {
            "id": str(row.id),
            "student_name": student.full_name_en,
            "parent_email": parent.email,
            "notes": data.notes,
        }

    async def command(
        self, action, school, data, actor, actor_name=None, resource=None
    ):
        self.actor_id = actor
        return await super().command(action, school, data, actor, actor_name, resource)

    async def _revoke_parent(self, school, data, resource):
        row = await self.get(TransportFamilyAccess, school, resource, True)
        if row.revoked_at:
            raise TransportConflict("This family access has already ended")
        row.revoked_at = now()
        await self.db.flush()
        return {"id": str(row.id), "status": "revoked", "notes": data.notes}

    async def families(self, school, page=1):
        query = (
            select(TransportFamilyAccess, Student.full_name_en, User.email)
            .join(
                Student,
                (Student.id == TransportFamilyAccess.student_id)
                & (Student.school_id == school),
            )
            .join(
                User,
                (User.id == TransportFamilyAccess.parent_id)
                & (User.school_id == school),
            )
            .where(
                TransportFamilyAccess.school_id == school,
                TransportFamilyAccess.revoked_at.is_(None),
            )
        )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            await self.db.execute(
                query.order_by(
                    TransportFamilyAccess.created_at.desc(), TransportFamilyAccess.id
                )
                .offset((page - 1) * 20)
                .limit(20)
            )
        ).all()
        return {
            "links": [
                {
                    "id": str(row.id),
                    "student_id": str(row.student_id),
                    "student_name": name,
                    "parent_email": email,
                    "notes": row.notes,
                    "created_at": row.created_at.isoformat(),
                }
                for row, name, email in rows
            ],
            "total": total,
        }

    def audit(self, school, trip, actor, action, result):
        self.db.add(
            TransportEvent(
                id=uuid4(),
                school_id=school,
                request_id=uuid4(),
                action=action,
                actor_id=actor.id,
                actor_name=actor.full_name_en,
                payload={"resource_id": str(trip.id)},
                result=result,
                before_values={},
            )
        )

    async def issue_phone(self, school, trip_id, label, actor):
        trip = await self.get(TransportTrip, school, trip_id, True)
        if trip.status != "in_progress":
            raise TransportConflict(
                "Phone sharing is available only during an open trip"
            )
        if not trip.snapshot.get("tracking_stops"):
            raise TransportConflict(
                "This legacy trip has no frozen tracking stops; use the office location record and enable phone sharing on the next dispatch"
            )
        await self.db.execute(
            update(TransportPhoneSession)
            .where(
                TransportPhoneSession.school_id == school,
                TransportPhoneSession.trip_id == trip.id,
                TransportPhoneSession.revoked_at.is_(None),
            )
            .values(revoked_at=now())
        )
        token = secrets.token_urlsafe(48)
        row = TransportPhoneSession(
            id=uuid4(),
            school_id=school,
            trip_id=trip.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            label=label,
            created_by=actor.id,
            expires_at=now() + timedelta(hours=8),
        )
        self.db.add(row)
        result = {
            "id": str(row.id),
            "label": label,
            "expires_at": row.expires_at.isoformat(),
        }
        self.audit(school, trip, actor, "phone_issued", result)
        await self.db.flush()
        return {**result, "token": token}

    async def revoke_phone(self, school, trip_id, actor):
        trip = await self.get(TransportTrip, school, trip_id, True)
        await self.db.execute(
            update(TransportPhoneSession)
            .where(
                TransportPhoneSession.school_id == school,
                TransportPhoneSession.trip_id == trip.id,
                TransportPhoneSession.revoked_at.is_(None),
            )
            .values(revoked_at=now())
        )
        self.audit(school, trip, actor, "phone_revoked", {"status": "revoked"})
        await self.db.flush()
        return {"status": "revoked"}

    async def phone(self, token, lock=False):
        if not token or not 40 <= len(token) <= 150:
            raise HTTPException(401, "A valid trip sharing code is required")
        row = await self.db.scalar(
            select(TransportPhoneSession).where(
                TransportPhoneSession.token_hash
                == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        if row is None:
            raise HTTPException(401, "This trip sharing code is invalid")
        # Lock trip before session on every write, matching issue/revoke/completion.
        trip = await self.get(TransportTrip, row.school_id, row.trip_id, lock)
        if lock:
            row = await self.get(TransportPhoneSession, row.school_id, row.id, True)
        if row.revoked_at or row.expires_at <= now() or trip.status != "in_progress":
            raise HTTPException(
                410,
                "Sharing has ended, expired or been replaced. Ask the transport office for a new trip link.",
            )
        return row, trip

    @staticmethod
    def phone_context(session, trip):
        return {
            "trip_id": str(trip.id),
            "vehicle_number": trip.snapshot["vehicle_number"],
            "run_name": trip.snapshot["run_name"],
            "direction": trip.direction,
            "sender_label": session.label,
            "expires_at": session.expires_at.isoformat(),
            "stops": trip.snapshot.get("tracking_stops", []),
            "progress": trip.tracking_progress or {},
            "send_interval_seconds": 10,
        }

    async def ingest(self, token, data):
        session, trip = await self.phone(token, True)
        stamp = now()
        if data.recorded_at > stamp + timedelta(
            seconds=15
        ) or data.recorded_at < stamp - timedelta(seconds=120):
            raise ValueError(
                "Send a current GPS fix; check the phone's automatic date and time"
            )
        row = await self.db.scalar(
            select(TransportLivePosition).where(
                TransportLivePosition.vehicle_id == trip.vehicle_id
            )
        )
        if row and row.school_id != trip.school_id:
            raise TransportConflict("Vehicle school reference requires office review")
        if row and row.trip_id == trip.id:
            if data.recorded_at <= row.recorded_at:
                return {
                    "accepted": False,
                    "reason": "duplicate_or_older",
                    "received_at": row.received_at.isoformat(),
                }
            if (stamp - row.received_at).total_seconds() < 5:
                raise HTTPException(
                    429,
                    "Wait before sending another GPS fix",
                    headers={"Retry-After": "5"},
                )
        if row is None:
            row = TransportLivePosition(
                id=uuid4(), school_id=trip.school_id, vehicle_id=trip.vehicle_id
            )
            self.db.add(row)
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        row.trip_id, row.session_id, row.received_at = trip.id, session.id, stamp
        await self.db.flush()
        return {"accepted": True, "received_at": stamp.isoformat()}

    async def progress(self, token, data):
        session, trip = await self.phone(token, True)
        current = trip.tracking_progress or {}
        stops = trip.snapshot.get("tracking_stops", [])
        target = next((stop for stop in stops if stop["id"] == str(data.stop_id)), None)
        if target is None:
            raise ValueError("Choose a stop from this trip")
        if (
            current.get("stop_id") == str(data.stop_id)
            and current.get("stage") == data.stage
        ):
            return current  # Lost-response retry does not advance twice.
        if current.get("version", 0) != data.version:
            raise TransportConflict(
                "Stop progress changed. Refresh before updating it."
            )
        stages = {"arriving": 0, "at_stop": 1, "departed": 2}
        if target["order"] < current.get("order", -1) or (
            target["order"] == current.get("order")
            and stages[data.stage] < stages[current["stage"]]
        ):
            raise TransportConflict("A stop update cannot move this journey backwards")
        result = {
            "stop_id": str(data.stop_id),
            "name": target["name"],
            "order": target["order"],
            "stage": data.stage,
            "version": current.get("version", 0) + 1,
            "updated_at": now().isoformat(),
        }
        trip.tracking_progress = result
        self.db.add(
            TransportEvent(
                id=uuid4(),
                school_id=trip.school_id,
                request_id=uuid4(),
                action="phone_stop",
                actor_id=session.created_by,
                actor_name=f"Trip phone: {session.label}",
                payload={"resource_id": str(trip.id), "session_id": str(session.id)},
                result=result,
                before_values=current,
            )
        )
        await self.db.flush()
        return result

    @staticmethod
    def fix_response(fix):
        if fix is None:
            return None
        return {
            "latitude": str(fix.latitude),
            "longitude": str(fix.longitude),
            "accuracy_m": str(fix.accuracy_m),
            "speed_mps": str(fix.speed_mps) if fix.speed_mps is not None else None,
            "heading": str(fix.heading) if fix.heading is not None else None,
            "recorded_at": fix.recorded_at.isoformat(),
            "received_at": fix.received_at.isoformat(),
        }

    def journey(self, trip, fix, passenger=None):
        family = passenger is not None
        # No post-journey or absent child's continued access to the vehicle.
        visible = trip.status == "in_progress" and (
            not family or passenger.status in ("pending", "boarded")
        )
        position = self.fix_response(fix) if visible else None
        stop = passenger.stop_snapshot if family else None
        progress = trip.tracking_progress or {}
        guidance = {
            "nearby": False,
            "distance_m": None,
            "stops_away": None,
            "stop_state": None,
        }
        if visible and stop:
            if (
                progress
                and (
                    now() - datetime.fromisoformat(progress["updated_at"])
                ).total_seconds()
                <= 300
            ):
                if stop.get("id") == progress.get("stop_id"):
                    guidance["stop_state"] = progress["stage"]
                    guidance["stops_away"] = 0
                elif stop.get("order", 0) > progress.get("order", 0):
                    guidance["stops_away"] = sum(
                        1
                        for item in trip.snapshot.get("tracking_stops", [])
                        if progress["order"] < item["order"] <= stop["order"]
                    )
                else:
                    guidance["stop_state"] = "passed"
            relevant = (
                trip.direction == "pickup" and passenger.status == "pending"
            ) or (trip.direction == "drop" and passenger.status == "boarded")
            if (
                fix
                and relevant
                and (now() - fix.recorded_at).total_seconds() <= 30
                and float(fix.accuracy_m) <= 100
                and stop.get("latitude") is not None
                and stop.get("longitude") is not None
            ):
                meters = distance_m(
                    fix.latitude, fix.longitude, stop["latitude"], stop["longitude"]
                )
                guidance["distance_m"] = meters
                guidance["nearby"] = meters <= 300 and guidance["stop_state"] not in (
                    "departed",
                    "passed",
                )
        return {
            "id": f"{trip.id}:{passenger.id}" if family else str(trip.id),
            "trip_id": str(trip.id),
            "run_name": trip.snapshot["run_name"],
            "route_name": trip.snapshot["route_name"],
            "vehicle_number": trip.snapshot["vehicle_number"],
            "direction": trip.direction,
            "status": trip.status,
            "date_bs": NepalCalendar.ad_to_bs(trip.date_ad),
            "started_at": trip.started_at.isoformat(),
            "position": position,
            "progress": None if family else progress,
            "stops": [] if family else trip.snapshot.get("tracking_stops", []),
            "child": {
                "id": str(passenger.student_id),
                "name": passenger.student_name,
                "status": passenger.status,
                "boarded_at": passenger.boarded_at.isoformat()
                if passenger.boarded_at
                else None,
                "alighted_at": passenger.alighted_at.isoformat()
                if passenger.alighted_at
                else None,
            }
            if family
            else None,
            "stop": stop,
            "guidance": guidance,
        }

    async def feed(self, user, page=1):
        school = user.school_id
        if staff_view(user):
            query = (
                select(TransportTrip, TransportLivePosition)
                .outerjoin(
                    TransportLivePosition,
                    (TransportLivePosition.trip_id == TransportTrip.id)
                    & (TransportLivePosition.school_id == school),
                )
                .where(
                    TransportTrip.school_id == school,
                    TransportTrip.status == "in_progress",
                )
            )
            audience = "staff"
        elif user.has_role("parent"):
            query = (
                select(TransportTrip, TransportLivePosition, TransportPassenger)
                .join(
                    TransportPassenger,
                    (TransportPassenger.trip_id == TransportTrip.id)
                    & (TransportPassenger.school_id == school),
                )
                .join(
                    TransportFamilyAccess,
                    (TransportFamilyAccess.student_id == TransportPassenger.student_id)
                    & (TransportFamilyAccess.school_id == school)
                    & (TransportFamilyAccess.parent_id == user.id)
                    & TransportFamilyAccess.revoked_at.is_(None),
                )
                .join(
                    Student,
                    (Student.id == TransportPassenger.student_id)
                    & (Student.school_id == school)
                    & Student.is_deleted.is_(False)
                    & Student.deleted_at.is_(None)
                    & (Student.status == StudentStatus.ACTIVE),
                )
                .outerjoin(
                    TransportLivePosition,
                    (TransportLivePosition.trip_id == TransportTrip.id)
                    & (TransportLivePosition.school_id == school),
                )
                .where(
                    TransportTrip.school_id == school,
                    or_(
                        TransportTrip.status == "in_progress",
                        TransportTrip.date_ad == today(),
                    ),
                )
            )
            audience = "family"
        else:
            raise HTTPException(
                403,
                "Live tracking requires school tracking permission or verified parent access",
            )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        ordering = [TransportTrip.started_at.desc(), TransportTrip.id]
        if audience == "family":
            ordering.append(TransportPassenger.id)
        rows = (
            await self.db.execute(
                query.order_by(*ordering).offset((page - 1) * 20).limit(20)
            )
        ).all()
        return {
            "audience": audience,
            "journeys": [self.journey(*row) for row in rows],
            "total": total,
            "page": page,
            "server_time": now().isoformat(),
            "refresh_seconds": 10,
        }
