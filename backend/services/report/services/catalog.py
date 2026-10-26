"""School office report definitions and exact source permissions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Definition:
    key: str
    title: str
    group: str
    permissions: tuple[str, ...]
    filters: tuple[str, ...]
    description: str
    statuses: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


DEFINITIONS = [
    Definition(
        "student_list",
        "Student directory",
        "Students",
        ("student:read",),
        ("grade", "section", "status"),
        "Current school directory, admission/EMIS references and class details.",
        ("active", "inactive", "transferred", "graduated", "dropped_out"),
    ),
    Definition(
        "enrollment",
        "Yearly enrollment register",
        "Students",
        ("student:read",),
        ("academic_year_bs", "grade", "section"),
        "Latest recorded enrollment per student for the selected BS year. Unrecorded enrollment is not invented.",
        required=("academic_year_bs",),
    ),
    Definition(
        "dropout",
        "Recorded dropout register",
        "Students",
        ("student:read",),
        ("academic_year_bs", "grade", "section"),
        "Students whose latest enrollment in the selected year is explicitly marked dropped.",
        required=("academic_year_bs",),
    ),
    Definition(
        "emis_annual",
        "EMIS preparation register",
        "Students",
        ("student:read", "report:emis"),
        ("academic_year_bs", "grade", "section"),
        "Enrollment and demographic data with missing-data flags. For school review; not a government upload template.",
        required=("academic_year_bs",),
    ),
    Definition(
        "transfer_certificate",
        "Student transfer record",
        "Students",
        ("student:read",),
        ("student_id",),
        "Single-student details for preparing a transfer document. School approval and signing remain manual.",
        required=("student_id",),
    ),
    Definition(
        "attendance_monthly",
        "Monthly attendance",
        "Academics",
        ("student:read", "attendance:report"),
        ("month_bs", "grade", "section", "period_number"),
        "Recorded daily or selected-period attendance. Holidays and unmarked days are not counted as absences.",
        required=("month_bs",),
    ),
    Definition(
        "exam_result",
        "Exam result register",
        "Academics",
        ("exam:read", "marks:read"),
        ("exam_id", "section"),
        "Stored calculated results, with the exam publication state clearly recorded.",
        required=("exam_id",),
    ),
    Definition(
        "fee_collection",
        "Cash / bank collection register",
        "Finance",
        ("fee:report",),
        ("academic_year_bs", "date_from_bs", "date_to_bs", "grade", "section"),
        "Receipt and refund movements within the selected Nepal civil dates, with exact NPR totals.",
        required=("date_from_bs", "date_to_bs"),
    ),
    Definition(
        "fee_outstanding",
        "Outstanding fee balances",
        "Finance",
        ("fee:report",),
        ("academic_year_bs", "grade", "section"),
        "Current ledger balances and overdue bills. This is not a reconstructed historical balance sheet.",
    ),
    Definition(
        "staff_summary",
        "Staff directory",
        "Operations",
        ("staff:read",),
        ("status",),
        "Current teaching and non-teaching staff records; salary and private contacts are excluded.",
        ("active", "on_leave", "resigned", "retired", "terminated"),
    ),
    Definition(
        "library_loans",
        "Library lending register",
        "Operations",
        ("library:read",),
        ("status",),
        "Recorded loans, due/return dates and recorded assessed fines; fines are not cash collection.",
        ("issued", "overdue", "returned", "lost"),
    ),
    Definition(
        "hostel_residents",
        "Hostel resident register",
        "Operations",
        ("hostel:read",),
        ("grade", "section", "status"),
        "Bed/room assignments and agreed charges, using retained allocation snapshots.",
        ("active", "vacated"),
    ),
    Definition(
        "transport_students",
        "Transport agreements",
        "Operations",
        ("transport:read",),
        ("grade", "section", "status"),
        "Student pickup/drop agreements and agreed monthly fares; excludes live GPS and parent links.",
        ("active", "ended", "needs_setup"),
    ),
    Definition(
        "transport_trips",
        "Transport trip register",
        "Operations",
        ("transport:read",),
        ("date_from_bs", "date_to_bs", "status"),
        "Dispatch/completion state, frozen crew/vehicle and aggregate passenger accounting.",
        ("in_progress", "completed", "cancelled"),
        ("date_from_bs", "date_to_bs"),
    ),
]
CATALOG = {item.key: item for item in DEFINITIONS}


def allowed(user, definition):
    return all(user.has_permission(code) for code in definition.permissions)
