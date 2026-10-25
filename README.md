# Nepal School Management System

A modular FastAPI monolith and a Next.js frontend for a multi-tenant school management platform.

## Local development

### Prerequisites

- Python 3.13
- Node.js 22.13 or a newer supported LTS release
- PostgreSQL 16 running on `localhost:5432`
- Redis 7 running on `localhost:6379`

Create the PostgreSQL user referenced by `DATABASE_URL` before starting. The default development credentials in `.env.example` are `postgres` / `postgres`; update them for your local installation.

### Quick start

On Windows:

```bat
start-local.bat
```

On macOS or Linux:

```bash
chmod +x start-local.sh
./start-local.sh
```

The launcher creates the Python virtual environment when needed, installs missing dependencies, creates JWT development keys, prepares the database, and starts the frontend plus the API.

- Frontend: http://localhost:3001
- API docs: http://localhost:8080/docs

Local development uses ports 3001 and 8080 so another project can use 3000 and 8000. The frontend proxies `/backend` requests to `BACKEND_URL`, configured in `frontend/.env.local` (see `frontend/.env.example`).

Press `Ctrl+C` on macOS/Linux, or close the service command windows on Windows, to stop the servers.

For normal browsing and LCP/performance measurements, run `start-local.bat preview` (Windows) or `./start-local.sh preview` (macOS/Linux). This builds every frontend route before starting the optimized server on port 3001. If the API is already running, use `npm --prefix frontend run preview` instead. Stop the existing frontend on port 3001 before switching modes.

The default development mode compiles routes on demand; the first visit after a restart or code change can include several seconds of compilation in its time to first byte. Use `npm --prefix frontend run dev` for editing with hot reload, and rebuild the preview after changing frontend code. No Redis application cache is needed for the optimized frontend.

### Manual setup

Copy `.env.example` to `.env`, adjust the local database credentials, and then run:

```bash
python -m venv backend/.venv
# Windows: backend\.venv\Scripts\activate
# macOS/Linux: source backend/.venv/bin/activate
python -m pip install -r backend/requirements-local.txt
npm --prefix frontend install

cd backend
python scripts/generate_jwt_keys.py
python scripts/setup_database.py
python -m uvicorn main:app --reload --port 8080
```

In another terminal:

```bash
npm --prefix frontend run dev
```

The domain packages under `backend/services/` are internal modules of this one API process. They keep business boundaries without introducing separate deployments.

Redis is reserved for ephemeral authentication state: sessions, revoked tokens, password-reset/email-verification tokens, and failed-login protection. Password hashes, account records, durable session/audit records, and all school data stay in PostgreSQL. Redis is not used for general application caching, ordinary API rate limiting, or job queues.

### Production layout

- Deploy one FastAPI application with PostgreSQL and Redis on the VPS. Deploy Next.js to Vercel and point `NEXT_PUBLIC_API_URL` at the Cloudflare-proxied API domain.
- Run database schema migrations with `alembic upgrade head` during deployment. The API does not create or alter tables at startup.
- Set `UPLOAD_DIR` to a private persistent directory outside `public_html`. Uploaded files are served only through authenticated API routes.
- Keep PostgreSQL close to FastAPI. The conservative default pool is suitable for a small VPS and can be tuned using `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`.
- Run `npm --prefix frontend run build` for production. The dashboard chart library is split into a deferred chunk and is not part of the initial page code.

Example production processes:

```bash
cd backend
alembic upgrade head
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
```

## Verification

```bash
backend/.venv/Scripts/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

On macOS/Linux, use `backend/.venv/bin/python` for the test command.

Performance changes, benchmark results, deployment steps and the Nepal academic
workflow review are documented in [docs/performance-review.md](docs/performance-review.md).

The completed school fee workflow, permissions, and accounting rules are documented
in [docs/fees-and-payments.md](docs/fees-and-payments.md).

The completed library workflow, lending rules, copy inventory, permissions and
migration are documented in [docs/library.md](docs/library.md).
