"""
Nepal School Management System - Exception Handler for Auth Service
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from shared.utils.exceptions import NepalSMSException


async def nepal_sms_exception_handler(
    request: Request,
    exc: NepalSMSException
) -> JSONResponse:
    """Handle Nepal SMS custom exceptions"""

    # Map exception codes to HTTP status codes
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
        "RECORD_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "DUPLICATE_RECORD": status.HTTP_409_CONFLICT,
        "DATABASE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    http_status = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(
        status_code=http_status,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )
