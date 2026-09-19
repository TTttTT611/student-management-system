# Student Management System

A small, self-contained student records system: FastAPI backend, plain HTML/CSS/JS frontend, MySQL database. Runs as a single service, deploys with one `docker compose up`, and needs no build step for the frontend.

Designed for small schools, training centers and university departments that need to keep student records, class rosters and grades without a full campus ERP.

## Table of contents

- [Features](#features)
- [Who is it for](#who-is-it-for)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Docker](#docker)
- [Configuration](#configuration)
- [Roles and permissions](#roles-and-permissions)
- [Data model](#data-model)
- [Excel import and export](#excel-import-and-export)
- [API overview](#api-overview)
- [Tests](#tests)
- [Project layout](#project-layout)
- [Performance and limits](#performance-and-limits)
- [Schema changes](#schema-changes)
- [Contributing](#contributing)
- [License](#license)

## Features

**Records**
- Students: number, name, age, gender, major, class; paginated list, keyword search, filter by class
- Classes: group students, see head counts
- Courses: code, name, credits
- Enrollments and grades: enroll a student in courses, record scores, see credits and average per student
- Statistics: totals and breakdowns by major, gender and class
- Excel import and export of student records

**Accounts and security**
- Sign-in with two roles: admin (full access) and viewer (read-only)
- Admins create users and reset passwords; every user can change their own password
- Passwords hashed with bcrypt
- Sessions in HttpOnly, SameSite cookies with sliding renewal; Bearer tokens also accepted for API clients
- Login rate limiting: 5 failures lock the username and IP for 15 minutes
- Audit log of every write request and login attempt (user, IP, request body with passwords masked), browsable by admins

**Operations**
- Database migrations with Alembic
- Docker Compose with MySQL, optional Caddy for automatic HTTPS
- Backup and restore scripts, systemd and nginx examples
- Demo data generator and load-test script
- API tests with pytest (SQLite in memory, no MySQL needed)

## Who is it for

The UI is for the people who *manage* student records: registrars, administrative staff, class teachers. There is no student-facing portal; students do not sign in. Two roles are enough for a small organisation: staff who edit, and staff who only look things up.

It is **not** a full academic management system: no timetabling, no course conflict checks, no tuition, no multi-campus or department-level permissions.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Database | MySQL 8 (SQLite for tests), Alembic migrations |
| Auth | PyJWT, bcrypt |
| Excel | openpyxl |
| Frontend | Vanilla HTML / CSS / JS, served by the backend as static files |
| Deployment | Docker Compose, Caddy or nginx, systemd |

## Quick start

Requires Python 3.11+ and a running MySQL 8 server.

1. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

2. Create the database

   ```bash
   mysql -u root -p < init.sql
   ```

3. Configure

   ```bash
   cp .env.example .env
   # edit DATABASE_URL, SECRET_KEY and ADMIN_PASSWORD at minimum
   ```

4. Run migrations

   ```bash
   alembic upgrade head
   ```

5. Start the server

   ```bash
   uvicorn backend.main:app --reload
   ```

6. Open <http://127.0.0.1:8000/> and sign in with the admin account from `.env` (default `admin / admin123`). The account is created only on first start when the `users` table is empty. Change the password right away via **Change password** in the top-right corner.

Interactive API docs: <http://127.0.0.1:8000/docs>

To try it with sample data:

```bash
python scripts/seed_demo.py 500     # only runs on an empty students table
```

## Docker

```bash
cp .env.example .env    # set MYSQL_ROOT_PASSWORD, SECRET_KEY, ADMIN_PASSWORD
docker compose up -d --build
```

Starts MySQL and the backend, runs migrations on startup, serves the app at <http://localhost:8000/>.

For a public deployment with automatic HTTPS, set `DOMAIN`, `COOKIE_SECURE=true` and `TRUST_PROXY=true` in `.env` and start with the `https` profile:

```bash
docker compose --profile https up -d --build
```

Backups, upgrades, systemd/nginx setup and troubleshooting are covered in [docs/DEPLOY.md](docs/DEPLOY.md).

## Configuration

All settings come from environment variables, optionally loaded from a `.env` file in the project root (see [.env.example](.env.example)).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://root:password@localhost:3306/student_db` | SQLAlchemy connection URL |
| `SECRET_KEY` | `dev-secret-change-me` | JWT signing key. **Must** be changed in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | Session lifetime; cookie sessions renew automatically while active |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS so the session cookie is never sent in clear text |
| `TRUST_PROXY` | `false` | Set `true` behind nginx / Caddy to read the client IP from `X-Forwarded-For` |
| `LOGIN_MAX_FAILURES` | `5` | Failed logins before a username / IP is locked |
| `LOGIN_LOCK_MINUTES` | `15` | Lock duration |
| `ADMIN_USERNAME` | `admin` | Default admin created on first start |
| `ADMIN_PASSWORD` | `admin123` | Default admin password |
| `CORS_ORIGINS` | *(empty)* | Comma-separated origins, only needed if the frontend is served from another origin |
| `MYSQL_ROOT_PASSWORD` | `root` | Used by `docker-compose.yml` only |
| `BACKUP_DIR`, `KEEP_DAYS` | `backups`, `30` | Used by `scripts/backup.sh` |

## Roles and permissions

| Action | Admin | Viewer |
|---|---|---|
| View students, classes, courses, grades, statistics | ✓ | ✓ |
| Create / edit / delete records | ✓ | – |
| Import / export Excel | ✓ | – |
| Enroll students, record scores | ✓ | – |
| Manage users, reset passwords | ✓ | – |
| View audit log | ✓ | – |
| Change own password | ✓ | ✓ |

Permissions are enforced on the server; the UI only hides buttons.

## Data model

```
users        id, username, password_hash, role (admin | user)
classes      id, name (unique), major
students     id, student_no (unique), name, age, gender (male | female), major, class_id → classes
courses      id, code (unique), name, credit
enrollments  id, student_id → students, course_id → courses, score (nullable); unique (student, course)
audit_logs   id, created_at, user_id, username, ip, method, path, status, detail
```

Deleting a class sets its students' `class_id` to NULL. Deleting a student or a course deletes their enrollments.

## Excel import and export

**Export** (`Export` button, admin only) downloads all students as `students.xlsx`.

**Import** (`Import` button, admin only) accepts an `.xlsx` file with exactly this header row:

| Student No | Name | Age | Gender | Major | Class |
|---|---|---|---|---|---|
| S001 | Alice Smith | 20 | female | Computer Science | CS-1 |

Rules:
- `Gender` must be `male` or `female`; `Age` must be 1–150
- `Major` and `Class` are optional; if `Class` is given it must already exist
- Rows whose `Student No` already exists are skipped, not updated
- The result reports how many rows were created, skipped and rejected, with a reason per rejected row

## API overview

All endpoints live under `/api`. After signing in the session is kept in an HttpOnly cookie that the browser sends automatically; API clients may instead use the token returned by login as `Authorization: Bearer <token>`. Every endpoint except login requires authentication; write operations require the admin role.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password` |
| Users (admin) | `GET/POST /auth/users`, `PUT /auth/users/{id}/password`, `DELETE /auth/users/{id}` |
| Students | `GET /students?page=&size=&keyword=&class_id=`, `GET/PUT/DELETE /students/{id}`, `POST /students`, `GET /students/export`, `POST /students/import` |
| Classes | `GET/POST /classes`, `GET/PUT/DELETE /classes/{id}` |
| Courses | `GET/POST /courses`, `GET/PUT/DELETE /courses/{id}` |
| Enrollments | `GET /enrollments?student_id=&course_id=`, `POST /enrollments`, `PUT/DELETE /enrollments/{id}` |
| Statistics | `GET /stats` |
| Audit log (admin) | `GET /audit-logs?page=&size=&username=` |
| Health | `GET /health` |

List endpoints that paginate return `{ "items": [...], "total": n, "page": p, "size": s }`. Errors return `{ "detail": "message" }` with a 4xx status; validation errors use FastAPI's standard 422 format. The full schema is available at `/docs`.

Example:

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'

curl -b cookies.txt 'http://127.0.0.1:8000/api/students?keyword=Smith&size=5'
```

## Tests

```bash
pytest
```

22 API tests covering auth (cookies, rate limiting, password changes), students (CRUD, validation, pagination, search, import/export), classes, courses, grades, statistics and the audit log. They run against an in-memory SQLite database, so no MySQL is required.

## Project layout

```
backend/
  main.py          # app wiring: middleware, routers, static files, startup
  config.py        # settings from .env / environment
  database.py      # engine and session
  models.py        # ORM models
  schemas.py       # Pydantic request/response models
  security.py      # password hashing, JWT, cookie session, auth dependencies
  ratelimit.py     # login failure rate limiter
  audit.py         # audit log middleware
  routers/         # endpoints: auth / students / classes / courses / enrollments / stats / audit
frontend/
  index.html       # single-page app
  app.js
  style.css
alembic/           # database migrations
tests/             # pytest API tests
scripts/
  backup.sh        # mysqldump to backups/, keeps KEEP_DAYS days
  restore.sh       # restore from a backup file
  seed_demo.py     # generate demo / load-test data
  loadtest.py      # concurrent load test with p50 / p95 report
deploy/            # nginx, Caddy and systemd examples
docs/DEPLOY.md     # deployment and operations guide
init.sql           # creates the database
Dockerfile, docker-compose.yml
```

## Performance and limits

Measured with 5,000 students and 25,000 enrollments at 20 concurrent clients (single uvicorn process, local MySQL): list and search endpoints answer in under 130 ms at p95 with 330–850 requests per second. See [docs/DEPLOY.md](docs/DEPLOY.md#9-performance-reference) for the full table and how to reproduce it.

Practical guidance:
- Up to roughly 100,000 students everything works as-is. Beyond that the substring search (`LIKE '%keyword%'`) is the first thing to slow down; add a full-text index.
- The theoretical cap is the 32-bit auto-increment key: about 2.1 billion rows per table. Switch `id` columns to `BIGINT` if you ever get close.
- The audit log grows without bound (one row per write). Add a scheduled `DELETE FROM audit_logs WHERE created_at < ...` if you need to cap it.
- The login rate limiter is in-process; with multiple uvicorn workers each process counts separately.

## Schema changes

After editing `backend/models.py`, generate and apply a migration:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Migration `0003` converts legacy Chinese gender labels written by earlier versions to `male` / `female`.

## Contributing

Issues and pull requests are welcome. Before opening a PR:

```bash
pytest                     # all tests pass
node --check frontend/app.js
```

Keep the frontend dependency-free (no build step) and put new endpoints in `backend/routers/` with tests in `tests/`.

## License

[MIT](LICENSE)
