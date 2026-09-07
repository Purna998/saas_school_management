"""
Nepal School Management System - Custom Exceptions
Application-specific exceptions for better error handling
"""

from typing import Optional, Any
from fastapi import HTTPException, status


class NepalSMSException(Exception):
    """Base exception for Nepal SMS"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.code = code or "NEPAL_SMS_ERROR"
        self.details = details or {}
        super().__init__(self.message)


# Authentication & Authorization Exceptions
class AuthenticationError(NepalSMSException):
    """Authentication failed"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="AUTH_FAILED")


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials"""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message)
        self.code = "INVALID_CREDENTIALS"


class InvalidTokenError(AuthenticationError):
    """Invalid or expired token"""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message)
        self.code = "INVALID_TOKEN"


class MFARequiredError(AuthenticationError):
    """MFA verification required"""

    def __init__(self, message: str = "MFA verification required"):
        super().__init__(message)
        self.code = "MFA_REQUIRED"


class InvalidMFACodeError(AuthenticationError):
    """Invalid MFA code"""

    def __init__(self, message: str = "Invalid MFA code"):
        super().__init__(message)
        self.code = "INVALID_MFA_CODE"


class MFAAlreadyEnabledError(NepalSMSException):
    """MFA is already enabled"""

    def __init__(self, message: str = "MFA is already enabled for this account"):
        super().__init__(message, code="MFA_ALREADY_ENABLED")


class MFANotEnabledError(NepalSMSException):
    """MFA is not enabled"""

    def __init__(self, message: str = "MFA is not enabled for this account"):
        super().__init__(message, code="MFA_NOT_ENABLED")


class AuthorizationError(NepalSMSException):
    """Authorization failed - insufficient permissions"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, code="FORBIDDEN")


class AccountLockedError(AuthenticationError):
    """Account locked due to failed login attempts"""

    def __init__(self, message: str = "Account locked due to failed login attempts"):
        super().__init__(message)
        self.code = "ACCOUNT_LOCKED"


# Tenant/School Exceptions
class TenantNotFoundError(NepalSMSException):
    """School/Tenant not found"""

    def __init__(self, school_id: str):
        super().__init__(
            f"School with ID {school_id} not found",
            code="TENANT_NOT_FOUND",
            details={"school_id": school_id},
        )


class TenantInactiveError(NepalSMSException):
    """School/Tenant is inactive"""

    def __init__(self, school_id: str):
        super().__init__(
            f"School {school_id} is inactive or suspended",
            code="TENANT_INACTIVE",
            details={"school_id": school_id},
        )


class HSNotEnabledError(NepalSMSException):
    """Higher Secondary (Grade 11-12) not enabled for this school"""

    def __init__(self, school_id: str):
        super().__init__(
            "Grade 11-12 (Higher Secondary) is not enabled for this school",
            code="HS_NOT_ENABLED",
            details={"school_id": school_id},
        )


class FeatureNotAvailableError(NepalSMSException):
    """Feature not available in current subscription plan"""

    def __init__(self, feature: str, required_plan: str):
        super().__init__(
            f"Feature '{feature}' requires '{required_plan}' plan",
            code="FEATURE_NOT_AVAILABLE",
            details={"feature": feature, "required_plan": required_plan},
        )


# Student Exceptions
class StudentNotFoundError(NepalSMSException):
    """Student not found"""

    def __init__(self, student_id: str):
        super().__init__(
            f"Student with ID {student_id} not found",
            code="STUDENT_NOT_FOUND",
            details={"student_id": student_id},
        )


class DuplicateEMISError(NepalSMSException):
    """Duplicate EMIS student ID"""

    def __init__(self, emis_id: str):
        super().__init__(
            f"EMIS ID {emis_id} already exists",
            code="DUPLICATE_EMIS_ID",
            details={"emis_id": emis_id},
        )


# Academic Exceptions
class GradeNotFoundError(NepalSMSException):
    """Grade not found"""

    def __init__(self, grade: str):
        super().__init__(
            f"Grade {grade} not found",
            code="GRADE_NOT_FOUND",
            details={"grade": grade},
        )


class SectionNotFoundError(NepalSMSException):
    """Section not found"""

    def __init__(self, section_id: str):
        super().__init__(
            f"Section {section_id} not found",
            code="SECTION_NOT_FOUND",
            details={"section_id": section_id},
        )


class FacultyNotFoundError(NepalSMSException):
    """Faculty not found (Grade 11-12)"""

    def __init__(self, faculty_id: str):
        super().__init__(
            f"Faculty {faculty_id} not found",
            code="FACULTY_NOT_FOUND",
            details={"faculty_id": faculty_id},
        )


class SubjectNotFoundError(NepalSMSException):
    """Subject not found"""

    def __init__(self, subject_id: str):
        super().__init__(
            f"Subject {subject_id} not found",
            code="SUBJECT_NOT_FOUND",
            details={"subject_id": subject_id},
        )


# Exam Exceptions
class ExamNotFoundError(NepalSMSException):
    """Exam not found"""

    def __init__(self, exam_id: str):
        super().__init__(
            f"Exam {exam_id} not found",
            code="EXAM_NOT_FOUND",
            details={"exam_id": exam_id},
        )


class ExamLockedError(NepalSMSException):
    """Exam is locked - cannot modify marks"""

    def __init__(self, exam_id: str):
        super().__init__(
            f"Exam {exam_id} is locked and cannot be modified",
            code="EXAM_LOCKED",
            details={"exam_id": exam_id},
        )


class InvalidMarksError(NepalSMSException):
    """Invalid marks entry"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="INVALID_MARKS", details=details)


# Validation Exceptions
class InvalidBSDateError(NepalSMSException):
    """Invalid Bikram Sambat date"""

    def __init__(self, date_str: str):
        super().__init__(
            f"Invalid BS date: {date_str}",
            code="INVALID_BS_DATE",
            details={"date_bs": date_str},
        )


class InvalidAcademicYearError(NepalSMSException):
    """Invalid academic year"""

    def __init__(self, academic_year: str):
        super().__init__(
            f"Invalid academic year: {academic_year}",
            code="INVALID_ACADEMIC_YEAR",
            details={"academic_year": academic_year},
        )


# Database Exceptions
class DatabaseError(NepalSMSException):
    """Database operation failed"""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, code="DATABASE_ERROR")


class RecordNotFoundError(NepalSMSException):
    """Record not found in database"""

    def __init__(self, model: str, identifier: str):
        super().__init__(
            f"{model} with identifier {identifier} not found",
            code="RECORD_NOT_FOUND",
            details={"model": model, "identifier": identifier},
        )


class DuplicateRecordError(NepalSMSException):
    """Duplicate record in database"""

    def __init__(self, model: str, field: str, value: Any):
        super().__init__(
            f"{model} with {field}='{value}' already exists",
            code="DUPLICATE_RECORD",
            details={"model": model, "field": field, "value": str(value)},
        )


# External Service Exceptions
class ExternalServiceError(NepalSMSException):
    """External service error"""

    def __init__(self, service: str, message: str):
        super().__init__(
            f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "error": message},
        )


class SMSGatewayError(ExternalServiceError):
    """SMS gateway error"""

    def __init__(self, message: str):
        super().__init__("SMS Gateway", message)
        self.code = "SMS_GATEWAY_ERROR"


class PaymentGatewayError(ExternalServiceError):
    """Payment gateway error"""

    def __init__(self, gateway: str, message: str):
        super().__init__(f"{gateway} Payment Gateway", message)
        self.code = "PAYMENT_GATEWAY_ERROR"


class EmailServiceError(ExternalServiceError):
    """Email service error"""

    def __init__(self, message: str):
        super().__init__("Email Service", message)
        self.code = "EMAIL_SERVICE_ERROR"


# File & Storage Exceptions
class FileUploadError(NepalSMSException):
    """File upload failed"""

    def __init__(self, message: str = "File upload failed"):
        super().__init__(message, code="FILE_UPLOAD_ERROR")


class InvalidFileTypeError(FileUploadError):
    """Invalid file type"""

    def __init__(self, file_type: str, allowed_types: list[str]):
        super().__init__(
            f"Invalid file type '{file_type}'. Allowed: {', '.join(allowed_types)}"
        )
        self.code = "INVALID_FILE_TYPE"
        self.details = {"file_type": file_type, "allowed_types": allowed_types}


class FileSizeExceededError(FileUploadError):
    """File size exceeded limit"""

    def __init__(self, size_mb: float, max_size_mb: int):
        super().__init__(f"File size {size_mb}MB exceeds limit of {max_size_mb}MB")
        self.code = "FILE_SIZE_EXCEEDED"
        self.details = {"size_mb": size_mb, "max_size_mb": max_size_mb}


# Convert custom exceptions to HTTP exceptions
def exception_to_http(exc: NepalSMSException) -> HTTPException:
    """Convert custom exception to FastAPI HTTPException"""
    status_code_map = {
        "AUTH_FAILED": status.HTTP_401_UNAUTHORIZED,
        "INVALID_CREDENTIALS": status.HTTP_401_UNAUTHORIZED,
        "INVALID_TOKEN": status.HTTP_401_UNAUTHORIZED,
        "MFA_REQUIRED": status.HTTP_401_UNAUTHORIZED,
        "INVALID_MFA_CODE": status.HTTP_401_UNAUTHORIZED,
        "ACCOUNT_LOCKED": status.HTTP_423_LOCKED,
        "FORBIDDEN": status.HTTP_403_FORBIDDEN,
        "TENANT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "TENANT_INACTIVE": status.HTTP_403_FORBIDDEN,
        "HS_NOT_ENABLED": status.HTTP_403_FORBIDDEN,
        "FEATURE_NOT_AVAILABLE": status.HTTP_403_FORBIDDEN,
        "STUDENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "DUPLICATE_EMIS_ID": status.HTTP_409_CONFLICT,
        "EXAM_LOCKED": status.HTTP_403_FORBIDDEN,
        "INVALID_BS_DATE": status.HTTP_400_BAD_REQUEST,
        "RECORD_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "DUPLICATE_RECORD": status.HTTP_409_CONFLICT,
        "DATABASE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "EXTERNAL_SERVICE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "FILE_UPLOAD_ERROR": status.HTTP_400_BAD_REQUEST,
        "INVALID_FILE_TYPE": status.HTTP_400_BAD_REQUEST,
        "FILE_SIZE_EXCEEDED": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    }

    status_code = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )
