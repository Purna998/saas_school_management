"""
Nepal School Management System - Shared Configuration Settings
Pydantic Settings with environment variable support
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application-wide configuration settings"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )

    # Application
    environment: str = Field(default="development", description="Environment: development/staging/production")
    debug: bool = Field(default=True, description="Debug mode")
    api_version: str = Field(default="v1", description="API version")
    app_name: str = Field(default="Nepal School Management System", description="Application name")
    secret_key: str = Field(default="change-this-secret-key", description="Application secret key")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/nepal_sms",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=10, description="Max overflow connections")
    database_pool_timeout_seconds: int = Field(default=30, description="Seconds to wait for a pooled connection")
    database_pool_recycle_seconds: int = Field(default=1800, description="Recycle pooled connections after this many seconds")
    database_command_timeout_seconds: int = Field(default=30, description="Maximum duration of a database command")
    database_echo: bool = Field(default=False, description="SQLAlchemy echo SQL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_cache_db: int = Field(default=1, description="Redis cache database")
    redis_session_db: int = Field(default=2, description="Redis session database")
    redis_queue_db: int = Field(default=3, description="Redis queue database")

    # JWT Configuration
    jwt_secret_key: str = Field(default="change-this-jwt-secret", description="JWT secret key")
    jwt_algorithm: str = Field(default="RS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(default=15, description="Access token expiry in minutes")
    jwt_refresh_token_expire_days: int = Field(default=7, description="Refresh token expiry in days")
    jwt_private_key_path: Optional[str] = Field(default="./keys/jwt_private.pem", description="JWT private key path")
    jwt_public_key_path: Optional[str] = Field(default="./keys/jwt_public.pem", description="JWT public key path")

    # MFA
    mfa_issuer_name: str = Field(default="Nepal SMS", description="MFA issuer name")
    mfa_digits: int = Field(default=6, description="MFA code digits")
    mfa_interval: int = Field(default=30, description="MFA time interval in seconds")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")

    # Nepal Timezone
    timezone: str = Field(default="Asia/Kathmandu", description="Nepal timezone (NPT UTC+5:45)")

    # AWS Configuration
    aws_region: str = Field(default="ap-south-1", description="AWS region (Mumbai - closest to Nepal)")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret key")
    s3_bucket_name: Optional[str] = Field(default=None, description="S3 bucket name")
    cloudfront_domain: Optional[str] = Field(default=None, description="CloudFront domain")

    # Email (Amazon SES)
    ses_region: str = Field(default="ap-south-1", description="SES region")
    ses_from_email: str = Field(default="noreply@nepalsms.com", description="From email address")
    ses_from_name: str = Field(default="Nepal SMS", description="From name")
    smtp_host: Optional[str] = Field(default=None, description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")

    # SMS Gateway - Sparrow SMS
    sparrow_sms_enabled: bool = Field(default=False, description="Enable Sparrow SMS")
    sparrow_sms_token: Optional[str] = Field(default=None, description="Sparrow SMS API token")
    sparrow_sms_from: str = Field(default="SCHOOLSMS", description="Sparrow SMS sender ID")
    sparrow_sms_api_url: str = Field(
        default="https://api.sparrowsms.com/v2/",
        description="Sparrow SMS API URL"
    )

    # SMS Gateway - Aakash SMS (Fallback)
    aakash_sms_enabled: bool = Field(default=False, description="Enable Aakash SMS")
    aakash_sms_token: Optional[str] = Field(default=None, description="Aakash SMS API token")
    aakash_sms_from: str = Field(default="SCHOOLSMS", description="Aakash SMS sender ID")
    aakash_sms_api_url: str = Field(
        default="https://api.aakashsms.com/",
        description="Aakash SMS API URL"
    )

    # Firebase Cloud Messaging
    fcm_enabled: bool = Field(default=False, description="Enable Firebase Cloud Messaging")
    fcm_project_id: Optional[str] = Field(default=None, description="Firebase project ID")
    fcm_credentials_path: Optional[str] = Field(
        default="./firebase-credentials.json",
        description="Firebase credentials JSON path"
    )

    # Payment Gateways (Disabled for now)
    payment_enabled: bool = Field(default=False, description="Enable payment gateways")

    # eSewa
    esewa_enabled: bool = Field(default=False, description="Enable eSewa")
    esewa_merchant_id: Optional[str] = Field(default=None, description="eSewa merchant ID")
    esewa_secret_key: Optional[str] = Field(default=None, description="eSewa secret key")
    esewa_api_url: str = Field(
        default="https://rc-epay.esewa.com.np/api/epay/",
        description="eSewa API URL"
    )
    esewa_sandbox: bool = Field(default=True, description="eSewa sandbox mode")

    # Khalti
    khalti_enabled: bool = Field(default=False, description="Enable Khalti")
    khalti_public_key: Optional[str] = Field(default=None, description="Khalti public key")
    khalti_secret_key: Optional[str] = Field(default=None, description="Khalti secret key")
    khalti_api_url: str = Field(default="https://khalti.com/api/v2/", description="Khalti API URL")
    khalti_sandbox: bool = Field(default=True, description="Khalti sandbox mode")

    # EMIS Integration
    emis_enabled: bool = Field(default=True, description="Enable EMIS integration")
    emis_api_url: Optional[str] = Field(default=None, description="EMIS API URL")
    emis_api_key: Optional[str] = Field(default=None, description="EMIS API key")

    # NEB Integration
    neb_enabled: bool = Field(default=True, description="Enable NEB integration")
    neb_api_url: Optional[str] = Field(default=None, description="NEB API URL")
    neb_api_key: Optional[str] = Field(default=None, description="NEB API key")

    # Monitoring
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    sentry_environment: str = Field(default="development", description="Sentry environment")
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus port")
    jaeger_enabled: bool = Field(default=True, description="Enable Jaeger tracing")
    jaeger_agent_host: str = Field(default="localhost", description="Jaeger agent host")
    jaeger_agent_port: int = Field(default=6831, description="Jaeger agent port")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(default=1000, description="Rate limit per hour")

    # Login Security
    max_login_attempts: int = Field(default=5, description="Max login attempts before lockout")
    login_lockout_duration_minutes: int = Field(
        default=15,
        description="Lockout duration in minutes"
    )

    # File Upload
    max_upload_size_mb: int = Field(default=10, description="Max upload size in MB")
    allowed_photo_extensions: List[str] = Field(
        default=["jpg", "jpeg", "png"],
        description="Allowed photo extensions"
    )
    allowed_document_extensions: List[str] = Field(
        default=["pdf", "doc", "docx", "xls", "xlsx"],
        description="Allowed document extensions"
    )

    # Report Generation
    report_temp_dir: str = Field(default="/tmp/nepal_sms_reports", description="Report temp directory")
    report_retention_days: int = Field(default=30, description="Report retention in days")

    # Background Jobs
    celery_broker_url: str = Field(
        default="redis://localhost:6379/3",
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/3",
        description="Celery result backend"
    )
    arq_redis_url: str = Field(default="redis://localhost:6379/4", description="ARQ Redis URL")

    # Service Ports (Development)
    auth_service_port: int = Field(default=8001, description="Auth service port")
    tenant_service_port: int = Field(default=8002, description="Tenant service port")
    student_service_port: int = Field(default=8003, description="Student service port")
    academic_service_port: int = Field(default=8004, description="Academic service port")
    attendance_service_port: int = Field(default=8005, description="Attendance service port")
    exam_service_port: int = Field(default=8006, description="Exam service port")
    fee_service_port: int = Field(default=8007, description="Fee service port")
    staff_service_port: int = Field(default=8008, description="Staff service port")
    communication_service_port: int = Field(default=8009, description="Communication service port")
    library_service_port: int = Field(default=8010, description="Library service port")
    transport_service_port: int = Field(default=8011, description="Transport service port")
    hostel_service_port: int = Field(default=8012, description="Hostel service port")
    inventory_service_port: int = Field(default=8013, description="Inventory service port")
    report_service_port: int = Field(default=8014, description="Report service port")
    notification_worker_port: int = Field(default=8015, description="Notification worker port")
    calendar_service_port: int = Field(default=8016, description="Calendar service port")

    # API Gateway
    api_gateway_url: str = Field(default="http://localhost:8000", description="API Gateway URL")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format: json or text")
    log_file_path: Optional[str] = Field(default="./logs/app.log", description="Log file path")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("allowed_photo_extensions", "allowed_document_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        """Parse extensions from comma-separated string or list"""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (replace asyncpg with psycopg2)"""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


# Global settings instance
settings = Settings()


# Service-specific configuration
class ServiceConfig:
    """Base configuration for individual services"""

    def __init__(self, service_name: str, service_port: int):
        self.service_name = service_name
        self.service_port = service_port
        self.settings = settings

    @property
    def service_title(self) -> str:
        """Get service title for API docs"""
        return f"{self.service_name.title()} Service - Nepal SMS"

    @property
    def service_description(self) -> str:
        """Get service description"""
        return f"{self.service_name.title()} microservice for Nepal School Management System"

    @property
    def api_prefix(self) -> str:
        """Get API prefix"""
        return f"/api/{settings.api_version}"
