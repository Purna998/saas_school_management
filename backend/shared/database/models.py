"""Import all domain models into the shared SQLAlchemy metadata."""

from services.academic.models import academic
from services.attendance.models import attendance
from services.auth.models import mfa, role, session, user
from services.communication.models import message
from services.exam.models import exam
from services.fee.models import fee
from services.hostel.models import hostel
from services.inventory.models import inventory
from services.library.models import library
from services.notification_worker.models import notification
from services.report.models import report
from services.staff.models import staff
from services.student.models import student
from services.tenant.models import tenant
from services.transport.models import transport


MODEL_MODULES = (
    academic,
    attendance,
    mfa,
    role,
    session,
    user,
    message,
    exam,
    fee,
    hostel,
    inventory,
    library,
    notification,
    report,
    staff,
    student,
    tenant,
    transport,
)
