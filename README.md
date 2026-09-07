# 🇳🇵 Nepal School Management System (SMS)

**FastAPI · Microservices · Multi-Tenant SaaS**

विद्यालय व्यवस्थापन प्रणाली — Technical Implementation

## 🎯 Project Overview

Production-grade, multi-tenant SaaS platform serving Nepali schools from ECD through Grade 12, fully compliant with NEB, EMIS, MOE, TSC, and DEO requirements.

### Architecture
- **Backend**: FastAPI 0.115+ (Python 3.12, Microservices)
- **Frontend**: Next.js 14 (App Router, TypeScript)
- **Mobile**: React Native + Expo (Android-first)
- **Database**: PostgreSQL 16 (RLS multi-tenancy), Redis 7, Elasticsearch 8
- **Infrastructure**: Docker, Kubernetes, AWS ap-south-1

## 📦 Microservices Architecture

| Service | Port | Responsibility |
|---------|------|----------------|
| auth-service | 8001 | JWT, MFA, RBAC, OAuth |
| tenant-service | 8002 | School onboarding, Grade 11-12 toggle |
| student-service | 8003 | Enrollment, EMIS, profiles |
| academic-service | 8004 | Grades, subjects, faculties, streams |
| attendance-service | 8005 | Daily/period attendance, reports |
| exam-service | 8006 | Exams, marks, GPA/Percentage engines |
| fee-service | 8007 | Fee structure, payments, receipts |
| staff-service | 8008 | Teachers, TSC, payroll |
| communication-service | 8009 | SMS, email, push notifications |
| library-service | 8010 | Book catalog, issue/return |
| transport-service | 8011 | Routes, vehicles, GPS |
| hostel-service | 8012 | Room allocation, warden |
| inventory-service | 8013 | Asset register, stock |
| report-service | 8014 | EMIS, analytics, PDFs |
| notification-worker | 8015 | Event processing |
| calendar-service | 8016 | BS/AD conversion, NPT |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 16
- Redis 7

### Development Setup

```bash
# Clone repository
git clone <repo-url>
cd saas_school_management_system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start infrastructure
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start services (development)
./scripts/start-dev.sh
```

## 🏗️ Project Structure

```
saas_school_management_system/
├── services/
│   ├── auth/                 # Authentication & Authorization
│   ├── tenant/              # School & Subscription Management
│   ├── student/             # Student Information System
│   ├── academic/            # Academic Management + Grade 11-12
│   ├── attendance/          # Attendance Tracking
│   ├── exam/               # Examination & Grading
│   ├── fee/                # Fee Management
│   ├── staff/              # Staff & Payroll
│   ├── communication/      # Notifications
│   ├── library/            # Library Management
│   ├── transport/          # Transport Management
│   ├── hostel/             # Hostel Management
│   ├── inventory/          # Inventory Management
│   ├── report/             # Reporting & Analytics
│   ├── notification_worker/ # Event Consumer
│   └── calendar/           # BS Calendar Service
├── shared/
│   ├── database/           # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── utils/              # Shared utilities
│   ├── middleware/         # Common middleware
│   └── config/             # Configuration
├── infrastructure/
│   ├── docker/             # Dockerfiles
│   ├── kubernetes/         # K8s manifests
│   └── helm/              # Helm charts
├── migrations/             # Alembic migrations
├── tests/                 # Test suites
├── scripts/               # Utility scripts
├── docker-compose.yml     # Local development
└── requirements.txt       # Python dependencies
```

## 🇳🇵 Nepal-Specific Features

### Grade 11-12 Toggle System
- **Feature Toggle**: Admin panel button to enable/disable Grade 11-12
- **Dynamic Tables**: `hs_faculties`, `hs_streams`, `hs_subjects`, `hs_enrollments`
- **Dual Grading**: GPA (1-10) vs Percentage (11-12)
- **Faculties**: Science, Management, Humanities, Education, Law

### Bikram Sambat Calendar
- Primary date system: BS (YYYY-MM-DD)
- AD dates stored internally, BS computed on read
- NPT timezone (UTC+5:45)
- Academic year: Baisakh to Chaitra

### EMIS Integration
- Annual survey export (JSON/Excel)
- Student enrollment by grade/gender/caste
- Dropout tracking with reason codes
- Teacher data with TSC numbers
- Attendance aggregation

## 🔐 Security

- **Multi-tenancy**: PostgreSQL Row-Level Security (RLS)
- **Auth**: JWT RS256, 15-min access + 7-day refresh
- **MFA**: TOTP for Admin/Accountant roles
- **Encryption**: TLS 1.3, AES-256 at rest
- **Compliance**: Nepal Privacy Act 2075, data residency SAARC

## 📊 API Documentation

Each service exposes OpenAPI documentation:
- Auth: http://localhost:8001/docs
- Tenant: http://localhost:8002/docs
- Student: http://localhost:8003/docs
- [...]

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html

# Run specific service tests
pytest tests/test_auth_service.py
```

## 📈 Monitoring

- **Metrics**: Prometheus + Grafana
- **Tracing**: Jaeger (OpenTelemetry)
- **Errors**: Sentry
- **Logs**: ELK Stack

## 🚢 Deployment

### Development
```bash
docker-compose up
```

### Staging/Production
```bash
# Build images
./scripts/build-all.sh

# Deploy to Kubernetes
kubectl apply -f infrastructure/kubernetes/

# Or use Helm
helm install nepal-sms infrastructure/helm/nepal-sms
```

## 📝 License

CONFIDENTIAL - Internal Use Only

## 👥 Team

Engineering & Architecture Team
Nepal School Management System

---

**Status**: 🚧 Active Development | **Version**: 1.0.0-alpha
