# Deployment & Operations Guide

For the people who deploy and maintain this system.

## 1. Requirements

- A Linux server (Ubuntu 22.04 / CentOS 8 or newer); 1 CPU / 1 GB RAM is plenty
- MySQL 8.0+
- Python 3.11+ (manual deployment) or Docker 24+ (container deployment)
- A domain name if the app is exposed to the internet (needed for HTTPS certificates)

## 2. Option A: Docker Compose (recommended)

```bash
git clone <repository-url> /opt/student-management
cd /opt/student-management
cp .env.example .env
```

Edit `.env` and change at least:

| Variable | Notes |
|---|---|
| `MYSQL_ROOT_PASSWORD` | database password |
| `SECRET_KEY` | generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_PASSWORD` | initial admin password; change it in the UI right after first sign-in |

**Internal network** (plain HTTP):

```bash
docker compose up -d --build
```

Open `http://<server-ip>:8000/`.

**Public internet** (automatic HTTPS): point your domain at the server, then add to `.env`:

```
DOMAIN=your.domain.com
COOKIE_SECURE=true
TRUST_PROXY=true
```

```bash
docker compose --profile https up -d --build
```

Caddy obtains a Let's Encrypt certificate automatically. Open `https://your.domain.com/`.

## 3. Option B: Manual (systemd + nginx)

```bash
# code and dependencies
git clone <repository-url> /opt/student-management
cd /opt/student-management
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env && vim .env        # set DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD

# database
mysql -u root -p < init.sql
venv/bin/alembic upgrade head

# service
sudo cp deploy/student-management.service /etc/systemd/system/
sudo chown -R www-data:www-data /opt/student-management
sudo systemctl daemon-reload
sudo systemctl enable --now student-management
sudo systemctl status student-management
```

Pick one reverse proxy for HTTPS:

- **nginx**: edit the domain in `deploy/nginx.conf`, copy it to `/etc/nginx/sites-available/`, run `certbot --nginx -d your.domain.com`
- **Caddy**: edit the domain in `deploy/Caddyfile`, run `caddy run --config deploy/Caddyfile`

Behind a reverse proxy set `COOKIE_SECURE=true` and `TRUST_PROXY=true` in `.env`, then `systemctl restart student-management`.

## 4. After the first sign-in

1. Sign in with the admin account from `.env`
2. Click **Change password** (top right) and replace the initial password
3. Create accounts for the actual users on the **Users** page; do not use the admin account for daily work

## 5. Backups

`scripts/backup.sh` dumps the database with `mysqldump` into `backups/` and keeps 30 days by default.

```bash
./scripts/backup.sh                 # manual deployment
USE_DOCKER=1 ./scripts/backup.sh    # Docker deployment
```

Daily backup at 02:00:

```bash
crontab -e
# add this line (prefix with USE_DOCKER=1 for Docker deployments)
0 2 * * * cd /opt/student-management && ./scripts/backup.sh >> backups/backup.log 2>&1
```

**Copy backups to another machine or object storage regularly.** Local backups do not survive a disk failure.

Restore:

```bash
./scripts/restore.sh backups/student_db_20260919_020000.sql.gz
```

## 6. Upgrading

```bash
cd /opt/student-management
./scripts/backup.sh                 # always back up first
git pull

# Docker
docker compose up -d --build        # migrations run automatically on start

# Manual
venv/bin/pip install -r requirements.txt
sudo systemctl restart student-management   # ExecStartPre runs alembic upgrade head
```

## 7. Routine checks

| Check | How |
|---|---|
| Service alive | `curl http://127.0.0.1:8000/api/health` returns `{"status":"ok"}` |
| Server logs | Docker: `docker compose logs -f backend`; systemd: `journalctl -u student-management -f` |
| Audit log | Sign in as admin and open **Audit Log**: every create/update/delete and login attempt with IP |
| Backups | look at `backups/backup.log` and confirm a new file appears every day |
| Disk space | `df -h` for the backup directory and the MySQL data directory |

## 8. Troubleshooting

**"Too many failed login attempts"**
Five consecutive failures for a username or IP lock it for 15 minutes (`LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` in `.env`). Restarting the service clears the lock immediately.

**Lost the admin password**
Another admin can reset it on the **Users** page. If there is only one admin, update the database directly:

```bash
venv/bin/python -c "from backend.security import hash_password; print(hash_password('new-password'))"
mysql -u root -p student_db -e "UPDATE users SET password_hash='<output above>' WHERE username='admin';"
```

**Signed out immediately after signing in over HTTPS**
Check that `.env` has `COOKIE_SECURE=true` and `TRUST_PROXY=true`, and that the proxy forwards the `X-Forwarded-Proto` header.

**Excel import fails**
The header row must match the export file exactly: `Student No, Name, Age, Gender, Major, Class`; gender must be `male` or `female`; class names must already exist; the upload size is limited by the reverse proxy (20 MB in the examples).

**Rate limiting does not work with multiple workers**
The limiter is in-process. With `uvicorn --workers N` or several instances each process counts separately. The default single-process deployment is unaffected; switch to Redis-backed storage if you need multiple workers.

## 9. Performance reference

After generating 5,000 students and 25,000 enrollments with `scripts/seed_demo.py 5000`, `scripts/loadtest.py` at 20 concurrent clients (local MySQL on a laptop, single uvicorn process):

| Endpoint | p50 | p95 | QPS |
|---|---|---|---|
| Student list (paginated) | 29–36 ms | 45–100 ms | 440–660 |
| Name / number search | 37–56 ms | 100–125 ms | 330–440 |
| Statistics | 38 ms | 99 ms | 410 |
| Class list | 21 ms | 43 ms | 850 |

A few dozen concurrent users on an internal network come nowhere near this. At 100k+ students the substring search (`LIKE '%keyword%'`) slows down; consider a full-text index then. To run your own test:

```bash
python scripts/seed_demo.py 5000          # only on an empty database
python scripts/loadtest.py http://127.0.0.1:8000 admin admin123 20 300
```
