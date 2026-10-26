"""Set-based report sources. Source rows are never joined to multiplying children."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Date,
    String,
    Numeric,
    cast,
    case,
    func,
    literal,
    select,
    union_all,
)
from services.student.models.student import Student as S, StudentEnrollment as E
from services.attendance.models.attendance import Attendance as A
from services.exam.models.exam import Exam, Result
from services.fee.models.fee import FeeLedger as L, FeePayment as P, FeeRefund as F
from services.staff.models.staff import Staff
from services.library.models.library import BookIssue
from services.hostel.models.hostel import RoomAllocation
from services.transport.models.transport import (
    StudentTransport,
    TransportTrip,
    TransportPassenger,
)
from shared.utils.nepali_calendar import NepalCalendar, NPT


def enum_text(column):
    return func.lower(cast(column, String))


def col(key, label, kind="text"):
    return {"key": key, "label": label, "kind": kind}


def years(value):
    start = int(value[:4])
    return (str(start), value, f"{start}/{start+1}", f"{start}/{(start+1)%100:02d}")


def school_today():
    return datetime.now(NPT).date()


@dataclass
class Source:
    query: object
    columns: list
    sums: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def directory(school, data):
    q = select(
        S.id.label("sort_id"),
        S.full_name_en.label("name"),
        S.full_name_np.label("name_np"),
        S.admission_number.label("admission"),
        S.emis_student_id.label("emis"),
        S.current_grade.label("grade"),
        S.current_section.label("section"),
        S.roll_number.label("roll"),
        enum_text(S.gender).label("gender"),
        enum_text(S.status).label("status"),
        S.admission_date_ad.label("admitted_bs"),
    ).where(S.school_id == school, S.deleted_at.is_(None), S.is_deleted.is_(False))
    if data.grade is not None:
        q = q.where(S.current_grade == data.grade)
    if data.section:
        q = q.where(S.current_section == data.section)
    if data.status:
        q = q.where(enum_text(S.status) == data.status)
    columns = [
        col("name", "Student"),
        col("name_np", "Name Nepali"),
        col("admission", "Admission no."),
        col("emis", "EMIS student ID"),
        col("grade", "Current grade", "integer"),
        col("section", "Section"),
        col("roll", "Roll", "integer"),
        col("gender", "Gender"),
        col("status", "Current status"),
        col("admitted_bs", "Admission BS", "bs_date"),
    ]
    if data.report_type == "transfer_certificate":
        q = q.where(S.id == data.student_id).add_columns(
            S.date_of_birth_ad.label("birth_bs"),
            S.previous_school_name.label("previous_school"),
        )
        columns += [
            col("birth_bs", "Birth date BS", "bs_date"),
            col("previous_school", "Previous school on record"),
        ]
    return Source(
        q.order_by(
            S.current_grade.asc().nullslast(),
            S.current_section,
            S.roll_number.asc().nullslast(),
            S.full_name_en,
            S.id,
        ),
        columns,
        notes=[
            "Current directory/class information; not a historical enrollment count."
        ]
        + (
            [
                "Transfer preparation record only. No certificate number, clearance, approval or signature is issued by this report."
            ]
            if data.report_type == "transfer_certificate"
            else []
        ),
    )


def enrollment(school, data):
    latest = (
        select(E)
        .where(
            E.school_id == school, E.academic_year_bs.in_(years(data.academic_year_bs))
        )
        .distinct(E.student_id)
        .order_by(
            E.student_id, E.enrolled_at.desc().nullslast(), E.created_at.desc(), E.id
        )
        .subquery()
    )
    q = (
        select(
            S.id.label("sort_id"),
            S.full_name_en.label("name"),
            S.full_name_np.label("name_np"),
            S.admission_number.label("admission"),
            S.emis_student_id.label("emis"),
            latest.c.grade,
            latest.c.section,
            enum_text(S.gender).label("gender"),
            enum_text(latest.c.status).label("status"),
            func.timezone("Asia/Kathmandu", latest.c.enrolled_at)
            .cast(Date)
            .label("enrolled_bs"),
        )
        .join(latest, latest.c.student_id == S.id)
        .where(S.school_id == school, S.deleted_at.is_(None), S.is_deleted.is_(False))
    )
    if data.grade is not None:
        q = q.where(latest.c.grade == data.grade)
    if data.section:
        q = q.where(latest.c.section == data.section)
    if data.report_type == "dropout":
        q = q.where(enum_text(latest.c.status) == "dropped")
    columns = [
        col("name", "Student"),
        col("name_np", "Name Nepali"),
        col("admission", "Admission no."),
        col("emis", "EMIS student ID"),
        col("grade", "Enrolled grade", "integer"),
        col("section", "Enrolled section"),
        col("gender", "Gender"),
        col("status", "Recorded enrollment status"),
        col("enrolled_bs", "Enrollment BS", "bs_date"),
    ]
    notes = [
        "Latest recorded enrollment per student in the selected BS year. Students without an enrollment record are excluded. Enrollment time is not a dropout/transfer date."
    ]
    if data.report_type == "emis_annual":
        q = q.add_columns(
            S.date_of_birth_ad.label("birth_bs"),
            enum_text(S.caste_ethnicity).label("ethnicity"),
            S.disability_type.label("disability"),
            S.nationality,
            func.concat_ws(
                "; ",
                case(
                    (
                        func.nullif(func.btrim(S.emis_student_id), "").is_(None),
                        "EMIS ID missing",
                    )
                ),
                case((S.caste_ethnicity.is_(None), "Ethnicity not recorded")),
                case((S.nationality.is_(None), "Nationality not recorded")),
            ).label("review"),
        )
        columns += [
            col("birth_bs", "Birth BS", "bs_date"),
            col("ethnicity", "Recorded caste/ethnicity"),
            col("disability", "Recorded disability (blank = unrecorded)"),
            col("nationality", "Nationality"),
            col("review", "Data review flags"),
        ]
        notes += [
            "EMIS preparation data only, not an official IEMIS upload or submitted Flash report. Reconcile current CEHRD requirements and missing records before entry. Blank disability does not certify no disability."
        ]
    return Source(
        q.order_by(latest.c.grade, latest.c.section, S.full_name_en, S.id),
        columns,
        notes=notes,
    )


def attendance(school, data):
    start = NepalCalendar.bs_to_ad(data.month_bs + "-01")
    y, m = map(int, data.month_bs.split("-"))
    end = NepalCalendar.bs_to_ad(
        f"{y+1 if m==12 else y:04d}-{1 if m==12 else m+1:02d}-01"
    )
    statuses = ("present", "absent", "late", "leave", "holiday")
    columns = (
        [
            col("name", "Student"),
            col("admission", "Admission no."),
            col("grade", "Recorded grade"),
            col("section", "Recorded section"),
        ]
        + [col(key, key.title(), "integer") for key in statuses]
        + [
            col("marked", "Recorded non-holiday days", "integer"),
            col("rate", "Present + late / recorded days %", "percent"),
        ]
    )
    counted = [
        func.count().filter(enum_text(A.status) == key).label(key) for key in statuses
    ]
    marked = func.count().filter(enum_text(A.status) != "holiday")
    rate = cast(
        (func.count().filter(enum_text(A.status).in_(("present", "late"))) * 100.0)
        / func.nullif(marked, 0),
        Numeric(7, 2),
    )
    q = (
        select(
            S.id.label("sort_id"),
            S.full_name_en.label("name"),
            S.admission_number.label("admission"),
            A.grade,
            A.section,
            *counted,
            marked.label("marked"),
            rate.label("rate"),
        )
        .join(S, (S.id == A.student_id) & (S.school_id == school))
        .where(
            A.school_id == school,
            A.date_ad >= start,
            A.date_ad < end,
            A.period_number == data.period_number
            if data.period_number
            else A.period_number.is_(None),
        )
    )
    if data.grade is not None:
        q = q.where(A.grade == str(data.grade))
    if data.section:
        q = q.where(A.section == data.section)
    q = q.group_by(
        S.id, S.full_name_en, S.admission_number, A.grade, A.section
    ).order_by(A.grade, A.section, S.full_name_en, S.id)
    return Source(
        q,
        columns,
        {key: key.title() for key in statuses}
        | {"marked": "Recorded non-holiday days"},
        [
            "Only recorded attendance rows are included. Unmarked days/students are not inferred absent. Leave counts in recorded non-holiday days; holidays do not. Daily and period attendance are never combined."
        ],
    )


def results(school, data):
    q = (
        select(
            Result.id.label("sort_id"),
            S.full_name_en.label("name"),
            S.admission_number.label("admission"),
            S.current_section.label("section"),
            Exam.name.label("exam"),
            Exam.grade,
            enum_text(Exam.status).label("publication"),
            Result.total_marks,
            Result.percentage,
            Result.gpa,
            Result.rank,
            enum_text(Result.status).label("status"),
        )
        .join(Exam, (Exam.id == Result.exam_id) & (Exam.school_id == school))
        .join(S, (S.id == Result.student_id) & (S.school_id == school))
        .where(
            Result.school_id == school,
            Result.exam_id == data.exam_id,
            Exam.deleted_at.is_(None),
        )
    )
    if data.section:
        q = q.where(S.current_section == data.section)
    return Source(
        q.order_by(Result.rank.asc().nullslast(), S.full_name_en, Result.id),
        [
            col("name", "Student"),
            col("admission", "Admission no."),
            col("section", "Current section"),
            col("exam", "Exam"),
            col("grade", "Exam grade", "integer"),
            col("publication", "Exam publication state"),
            col("total_marks", "Stored total marks", "decimal"),
            col("percentage", "Stored percentage", "percent"),
            col("gpa", "Stored GPA", "decimal"),
            col("rank", "Stored rank", "integer"),
            col("status", "Stored result"),
        ],
        notes=[
            "Stored calculated results only; no rank/GPA recalculation. Unpublished exams remain clearly labelled. Student names/sections are current directory values at report generation."
        ],
    )


def collections(school, data):
    start, end = (
        NepalCalendar.bs_to_ad(data.date_from_bs),
        NepalCalendar.bs_to_ad(data.date_to_bs),
    )
    common = [L.school_id == school, S.school_id == school]
    if data.academic_year_bs:
        common.append(L.academic_year_bs.in_(years(data.academic_year_bs)))
    if data.grade is not None:
        common.append(S.current_grade == data.grade)
    if data.section:
        common.append(S.current_section == data.section)
    payment = (
        select(
            P.id.label("sort_id"),
            P.paid_date_ad.label("date_ad"),
            P.paid_date_ad.label("date_bs"),
            literal("receipt").label("kind"),
            P.receipt_number.label("number"),
            S.full_name_en.label("name"),
            S.admission_number.label("admission"),
            L.fee_head_name.label("head"),
            enum_text(P.payment_method).label("method"),
            P.amount.label("gross"),
            literal(Decimal("0.00"), type_=Numeric(12, 2)).label("refunded"),
            P.amount.label("net"),
        )
        .join(L, (L.id == P.ledger_id) & (L.student_id == P.student_id))
        .join(S, S.id == P.student_id)
        .where(P.school_id == school, P.paid_date_ad.between(start, end), *common)
    )
    refund = (
        select(
            F.id.label("sort_id"),
            F.refunded_date_ad.label("date_ad"),
            F.refunded_date_ad.label("date_bs"),
            literal("refund").label("kind"),
            F.refund_number.label("number"),
            S.full_name_en.label("name"),
            S.admission_number.label("admission"),
            L.fee_head_name.label("head"),
            enum_text(F.payment_method).label("method"),
            literal(Decimal("0.00"), type_=Numeric(12, 2)).label("gross"),
            F.amount.label("refunded"),
            (-F.amount).label("net"),
        )
        .join(
            P,
            (P.id == F.payment_id)
            & (P.school_id == school)
            & (P.student_id == F.student_id),
        )
        .join(L, (L.id == P.ledger_id) & (L.student_id == F.student_id))
        .join(S, S.id == F.student_id)
        .where(F.school_id == school, F.refunded_date_ad.between(start, end), *common)
    )
    movement = union_all(payment, refund).subquery()
    return Source(
        select(movement).order_by(
            movement.c.date_ad, movement.c.kind, movement.c.sort_id
        ),
        [
            col("date_bs", "Movement date BS", "bs_date"),
            col("date_ad", "Movement date AD", "date"),
            col("kind", "Movement"),
            col("number", "Receipt / refund no."),
            col("name", "Student"),
            col("admission", "Admission no."),
            col("head", "Fee head"),
            col("method", "Method"),
            col("gross", "Gross received NPR", "money"),
            col("refunded", "Refunded NPR", "money"),
            col("net", "Net movement NPR", "money"),
        ],
        {
            "gross": "Gross receipts NPR",
            "refunded": "Refunds NPR",
            "net": "Net cash/bank movement NPR",
        },
        [
            "Receipts and refunds are filtered by their own movement dates. A refund today may relate to an older receipt. Concessions, billed fees and agreed service charges are not cash collection. Grade/section are current directory filters."
        ],
    )


def outstanding(school, data):
    q = (
        select(
            S.id.label("sort_id"),
            S.full_name_en.label("name"),
            S.admission_number.label("admission"),
            S.current_grade.label("grade"),
            S.current_section.label("section"),
            func.sum(L.amount_due).label("due"),
            func.sum(L.amount_paid).label("paid"),
            func.sum(L.balance).label("balance"),
            func.coalesce(
                func.sum(L.balance).filter(L.due_date_ad < school_today()), 0
            ).label("overdue"),
        )
        .join(S, (S.id == L.student_id) & (S.school_id == school))
        .where(L.school_id == school)
    )
    if data.academic_year_bs:
        q = q.where(L.academic_year_bs.in_(years(data.academic_year_bs)))
    if data.grade is not None:
        q = q.where(S.current_grade == data.grade)
    if data.section:
        q = q.where(S.current_section == data.section)
    return Source(
        q.group_by(
            S.id, S.full_name_en, S.admission_number, S.current_grade, S.current_section
        )
        .having(func.sum(L.balance) > 0)
        .order_by(func.sum(L.balance).desc(), S.id),
        [
            col("name", "Student"),
            col("admission", "Admission no."),
            col("grade", "Current grade", "integer"),
            col("section", "Current section"),
            col("due", "Net billed NPR", "money"),
            col("paid", "Net allocated payments NPR", "money"),
            col("balance", "Outstanding NPR", "money"),
            col("overdue", "Overdue NPR", "money"),
        ],
        {"balance": "Current outstanding NPR", "overdue": "Current overdue NPR"},
        [
            "Current balances as at generation, not a historical reconstruction. Bills are aggregated before any payment joins."
        ],
    )


def operations(school, data):
    kind = data.report_type
    if kind == "staff_summary":
        q = select(
            Staff.id.label("sort_id"),
            Staff.full_name_en.label("name"),
            Staff.full_name_np.label("name_np"),
            Staff.employee_id.label("reference"),
            enum_text(Staff.staff_type).label("type"),
            Staff.designation,
            Staff.department,
            Staff.qualification,
            enum_text(Staff.status).label("status"),
            Staff.joined_date_ad.label("joined_bs"),
        ).where(
            Staff.school_id == school,
            Staff.deleted_at.is_(None),
            Staff.is_deleted.is_(False),
        )
        if data.status:
            q = q.where(enum_text(Staff.status) == data.status)
        return Source(
            q.order_by(Staff.full_name_en, Staff.id),
            [
                col("name", "Staff"),
                col("name_np", "Name Nepali"),
                col("reference", "Employee ID"),
                col("type", "Staff type"),
                col("designation", "Designation"),
                col("department", "Department"),
                col("qualification", "Qualification"),
                col("status", "Status"),
                col("joined_bs", "Joined BS", "bs_date"),
            ],
            notes=[
                "Current directory, excluding salary, DOB and private contacts. No payroll or statutory TDS calculations are implied."
            ],
        )
    if kind == "library_loans":
        model = BookIssue
        effective = case(
            (
                enum_text(model.status).in_(("issued", "overdue"))
                & (model.due_date_ad < school_today()),
                "overdue",
            ),
            else_=enum_text(model.status),
        )
        q = select(
            model.id.label("sort_id"),
            model.book_title.label("book"),
            model.accession_number.label("accession"),
            model.borrower_name.label("name"),
            model.borrower_reference.label("reference"),
            enum_text(model.issued_to_type).label("type"),
            model.issue_date_ad.label("issued_bs"),
            model.due_date_ad.label("due_bs"),
            model.return_date_ad.label("returned_bs"),
            effective.label("status"),
            model.fine_amount.label("fine"),
        ).where(model.school_id == school)
        if data.status:
            q = q.where(effective == data.status)
        return Source(
            q.order_by(model.issue_date_ad.desc(), model.id),
            [
                col("book", "Book"),
                col("accession", "Accession"),
                col("name", "Borrower"),
                col("reference", "Borrower reference"),
                col("type", "Borrower type"),
                col("issued_bs", "Issued BS", "bs_date"),
                col("due_bs", "Due BS", "bs_date"),
                col("returned_bs", "Returned BS", "bs_date"),
                col("status", "State at generation"),
                col("fine", "Recorded assessed fine NPR", "money"),
            ],
            {"fine": "Recorded assessed fines NPR"},
            [
                "Loan snapshots are retained. Open-loan overdue state uses the generation date. Recorded fines are assessed amounts, not proof of payment or accrued estimates."
            ],
        )
    model = RoomAllocation if kind == "hostel_residents" else StudentTransport
    q = (
        select(
            model.id.label("sort_id"),
            model.student_name.label("name")
            if kind == "hostel_residents"
            else model.snapshot["student_name"].astext.label("name"),
            S.current_grade.label("grade"),
            S.current_section.label("section"),
            model.monthly_fee.label("fare"),
        )
        .outerjoin(S, (S.id == model.student_id) & (S.school_id == school))
        .where(model.school_id == school)
    )
    if data.grade is not None:
        q = q.where(S.current_grade == data.grade)
    if data.section:
        q = q.where(S.current_section == data.section)
    columns = [
        col("name", "Student snapshot"),
        col("grade", "Current grade", "integer"),
        col("section", "Current section"),
    ]
    if kind == "hostel_residents":
        q = q.add_columns(
            model.hostel_name.label("hostel"),
            model.room_number.label("room"),
            model.bed_label.label("bed"),
            enum_text(model.status).label("status"),
            model.allocated_date_ad.label("start_bs"),
            model.vacated_date_ad.label("end_bs"),
        )
        if data.status:
            q = q.where(enum_text(model.status) == data.status)
        columns += [col("hostel", "Hostel"), col("room", "Room"), col("bed", "Bed")]
    else:
        state = case(
            (model.needs_setup.is_(True) & model.is_active.is_(True), "needs_setup"),
            (model.is_active.is_(True), "active"),
            else_="ended",
        )
        q = q.add_columns(
            state.label("status"),
            enum_text(model.transport_type).label("service"),
            model.start_date_ad.label("start_bs"),
            model.end_date_ad.label("end_bs"),
            model.snapshot["pickup"]["stop_name"].astext.label("pickup"),
            model.snapshot["drop"]["stop_name"].astext.label("drop"),
        )
        if data.status:
            q = q.where(state == data.status)
        columns += [
            col("service", "Service"),
            col("pickup", "Pickup snapshot"),
            col("drop", "Drop snapshot"),
        ]
    columns += [
        col("status", "State"),
        col("start_bs", "Starts BS", "bs_date"),
        col("end_bs", "Ends BS", "bs_date"),
        col("fare", "Agreed monthly charge NPR", "money"),
    ]
    return Source(
        q.order_by(model.created_at.desc(), model.id),
        columns,
        notes=[
            "Retained agreement/allocation snapshots. Monthly charges are agreed service rates, not billed amounts or collected revenue. Grade/section are current directory values."
        ],
    )


def trips(school, data):
    counts = (
        select(
            TransportPassenger.trip_id,
            func.count().label("passengers"),
            *[
                func.count().filter(TransportPassenger.status == key).label(key)
                for key in ("pending", "boarded", "alighted", "absent")
            ],
        )
        .where(TransportPassenger.school_id == school)
        .group_by(TransportPassenger.trip_id)
        .subquery()
    )
    t = TransportTrip
    q = (
        select(
            t.id.label("sort_id"),
            t.date_ad.label("date_bs"),
            t.snapshot["run_name"].astext.label("run"),
            t.snapshot["vehicle_number"].astext.label("vehicle"),
            t.snapshot["driver_name"].astext.label("driver"),
            t.direction,
            t.status,
            *[
                func.coalesce(counts.c[key], 0).label(key)
                for key in ("passengers", "pending", "boarded", "alighted", "absent")
            ],
            case(
                (t.sweep_confirmed.is_(True), "confirmed"), else_="not confirmed"
            ).label("sweep"),
        )
        .outerjoin(counts, counts.c.trip_id == t.id)
        .where(
            t.school_id == school,
            t.date_ad.between(
                NepalCalendar.bs_to_ad(data.date_from_bs),
                NepalCalendar.bs_to_ad(data.date_to_bs),
            ),
        )
    )
    if data.status:
        q = q.where(t.status == data.status)
    return Source(
        q.order_by(t.date_ad.desc(), t.id),
        [
            col("date_bs", "Trip BS", "bs_date"),
            col("run", "Run snapshot"),
            col("vehicle", "Vehicle snapshot"),
            col("driver", "Driver snapshot"),
            col("direction", "Direction"),
            col("status", "Trip state"),
        ]
        + [
            col(key, key.title(), "integer")
            for key in ("passengers", "pending", "boarded", "alighted", "absent")
        ]
        + [col("sweep", "Empty-vehicle check")],
        {
            "passengers": "Roster entries",
            "pending": "Pending entries",
            "boarded": "Currently on board entries",
        },
        [
            "Trip/passenger state is frozen when this report is saved. No vehicle coordinates, tracker codes or parent links are exported. Cancelled entries remain in total roster counts."
        ],
    )


def build(school, data):
    kind = data.report_type
    if kind in ("student_list", "transfer_certificate"):
        return directory(school, data)
    if kind in ("enrollment", "dropout", "emis_annual"):
        return enrollment(school, data)
    if kind == "attendance_monthly":
        return attendance(school, data)
    if kind == "exam_result":
        return results(school, data)
    if kind == "fee_collection":
        return collections(school, data)
    if kind == "fee_outstanding":
        return outstanding(school, data)
    if kind == "transport_trips":
        return trips(school, data)
    return operations(school, data)
