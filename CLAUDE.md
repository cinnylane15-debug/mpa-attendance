# MPA Attendance Project

## Overview

School attendance management system using face recognition from Dahua IP cameras.
Built with FastAPI (backend), React + Ant Design (frontend), PostgreSQL + pgvector, Redis, and InsightFace.

## Project Structure

```
mpa-attendance/
├── app/                    # FastAPI backend
│   ├── main.py             # App entry point, router registration
│   ├── config.py           # Settings (env vars, defaults)
│   ├── database.py         # SQLAlchemy engine, session, migrations
│   ├── models.py           # All SQLAlchemy models
│   ├── schemas.py          # All Pydantic schemas
│   ├── auth.py             # JWT auth, password hashing, dependencies
│   ├── face_engine.py      # InsightFace wrapper (embedding extraction)
│   ├── rtsp_worker.py      # Camera workers (snapshot + RTSP capture, face matching, attendance recording)
│   └── routers/
│       ├── auth_router.py  # Login, token refresh, user info
│       ├── students.py     # CRUD + photo upload + face enrollment
│       ├── classes.py      # CRUD
│       ├── attendance.py   # Today/history records, manual check-in/out, Excel export, live detections
│       ├── cameras.py      # CRUD + start/stop/test workers
│       ├── schedules.py    # Class schedule CRUD
│       ├── holidays.py     # Holiday CRUD
│       ├── dashboard.py    # Stats, weekly summary, class stats
│       └── unknown_faces.py # Unknown face library (assign/dismiss/delete)
├── frontend/               # React (Vite) frontend
│   ├── src/
│   │   ├── App.jsx         # Routes
│   │   ├── api.js          # API client (fetch wrapper with auth)
│   │   ├── context/AuthContext.jsx
│   │   ├── components/
│   │   │   ├── AppLayout.jsx    # Sidebar + header layout
│   │   │   └── ProtectedRoute.jsx
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── Students.jsx
│   │       ├── Classes.jsx
│   │       ├── Attendance.jsx
│   │       ├── Cameras.jsx
│   │       ├── Schedules.jsx
│   │       ├── Holidays.jsx
│   │       ├── UnknownFaces.jsx
│   │       └── Login.jsx
│   └── package.json
├── docker/
│   ├── Dockerfile.backend   # Python 3.12 + pip install
│   ├── Dockerfile.frontend  # Node build → nginx
│   └── nginx.conf           # Frontend nginx (proxies /api/ and /uploads/ to backend)
├── docker-compose.yml       # All services: db, redis, backend, frontend
└── CLAUDE.md
```

## Architecture

- **Frontend** (port 3000): React SPA served by nginx, proxies `/api/` and `/uploads/` to backend
- **Backend** (port 8000): FastAPI with Uvicorn, serves API and uploaded files at `/uploads/`
- **PostgreSQL 16** (port 5432): With pgvector extension for face embedding similarity search
- **Redis 7** (port 6379): Available for caching (not heavily used yet)

## MPA Attendance API Endpoints

All endpoints prefixed with `/api/` except `/health`. All require JWT auth except `/health` and `/api/auth/login`.

### Auth (`/api/auth`)
- `POST /login` — `{"username", "password"}` → `{"access_token", "token_type"}`
- `GET /me` — current user info

### Students (`/api/students`)
- `GET /` — list (query: `class_id`, `is_active`, `search`)
- `POST /` — create `{"student_id", "name", "class_id?", ...}`
- `GET /{id}` / `PUT /{id}` / `DELETE /{id}`
- `POST /{id}/photo` — upload face photo (multipart), extracts face embedding

### Classes (`/api/classes`)
- `GET /` / `POST /` / `GET /{id}` / `PUT /{id}` / `DELETE /{id}`

### Attendance (`/api/attendance`)
- `GET /today` — today's records
- `GET /records` — filtered (query: `date`, `class_id`, `student_id`)
- `POST /check-in` — `{"student_id": "STU001"}` (manual)
- `POST /check-out` — `{"student_id": "STU001"}` (manual)
- `GET /live` — recent RTSP/snapshot detections (last 5 min)
- `GET /export` — Excel download (query: `start_date`, `end_date`, `class_id?`)

### Cameras (`/api/cameras`)
- `GET /` / `POST /` / `GET /{id}` / `PUT /{id}` / `DELETE /{id}`
- `POST /{id}/start` — start capture worker
- `POST /{id}/stop` — stop capture worker
- `POST /{id}/test` — test connection (snapshot or RTSP)
- `GET /{id}/status` — check if worker is running
- Camera fields: `name`, `location`, `rtsp_url`, `direction` (entry/exit), `capture_mode` (snapshot/rtsp), `snapshot_url?`

### Schedules (`/api/schedules`)
- `GET /` — list (query: `class_id`)
- `POST /` / `GET /{id}` / `PUT /{id}` / `DELETE /{id}`

### Holidays (`/api/holidays`)
- `GET /` / `POST /` / `GET /{id}` / `PUT /{id}` / `DELETE /{id}`
- `GET /upcoming` — next 5 holidays

### Dashboard (`/api/dashboard`)
- `GET /stats` — today's attendance stats
- `GET /weekly` — 7-day summary
- `GET /class-stats` — per-class breakdown

### Unknown Faces (`/api/unknown-faces`)
- `GET /` — list (query: `resolved`, `limit`)
- `GET /stats` — `{"total", "unresolved"}`
- `POST /{id}/assign` — `{"student_id"}` (assigns face to student, auto-enrolls embedding)
- `POST /{id}/dismiss` — mark as resolved without assigning
- `DELETE /{id}` — delete face and image

## Camera Capture Modes

- **snapshot** (default, recommended): Grabs JPEG via HTTP Digest auth from Dahua's `/cgi-bin/snapshot.cgi?channel=N`. Auto-derived from RTSP URL.
- **rtsp**: Continuous video stream via OpenCV. More complex, prone to connection issues.

Dahua RTSP URL format: `rtsp://admin:pass@IP:554/cam/realmonitor?channel=N&subtype=0`
Derived snapshot URL: `http://admin:pass@IP/cgi-bin/snapshot.cgi?channel=N`

## Face Recognition

- **Engine**: InsightFace with `buffalo_sc` model (512-dim embeddings)
- **Storage**: pgvector column on `students` table
- **Matching**: Cosine similarity via pgvector `<=>` operator
- **Threshold**: `FACE_RECOGNITION_TOLERANCE` (default 0.4)
- **Unknown faces**: Faces below threshold saved to `unknown_faces` table with cropped image

## Database Models

- `User` — admin/teacher accounts
- `Class` — school classes (has students, schedules)
- `Student` — student info + face_embedding (Vector 512) + photo_path
- `AttendanceRecord` — check-in/out records with status, method, confidence
- `Camera` — IP camera config (RTSP URL, capture mode, direction)
- `Schedule` — class timetable (day, start/end time)
- `Holiday` — school holidays
- `UnknownFace` — unidentified face captures from cameras

## Server Management API

- **Base URL**: `https://mpa.osetec.net`
- **Access Method**: Use `WebFetch` tool (curl does not work from this environment due to proxy restrictions)
- **Auth**: JWT Bearer token or X-API-Key header

### Credentials

- Server management: Username `admin` / Password `vdIwqkLoeMNhF4TP7Lwq`
- PostgreSQL: `mpa_admin` / `MpaSecure2026x` (database: `mpa_attendance`)
- Redis: `MpaRedis2026x`

### Gateway (`/gw`) — GET-based endpoints for proxy-restricted environments

- `GET /gw/login?username=...&password=...` — login via GET, returns tokens
- `GET /gw/exec?token=...&cmd=...&timeout=120` — execute command via GET
- `GET /gw/file/read?token=...&path=...` — read file via GET
- `GET /gw/file/write?token=...&path=...&content=...` — write file via GET

**Important notes for gateway usage:**
- Use `sh /path/to/script.sh` to run scripts (Cloudflare WAF blocks `bash` in URLs)
- For long-running commands, use `systemd-run sh /path/to/script.sh` to run in background
- Write status to a file (e.g., `echo DONE > /path/status`) to check completion
- WebFetch has a 15-minute cache — add `&_cb=N` to bust cache
- Some commands with special characters get blocked by Cloudflare WAF — write to script files first
- The `+` sign in URLs is interpreted as space — use `%2B` or avoid in content

### Server Details

- **Server IP**: `72.255.61.75`
- **App URL**: `http://72.255.61.75:3000` (frontend)
- **Management API**: runs on port `4433` locally, exposed via Cloudflare Tunnel
- **App code**: `/opt/mpa-app` on the server
- **GitHub repo**: `cinnylane15-debug/mpa-attendance` (public, server can `git pull`)

## Deployment

```sh
# On the server at /opt/mpa-app:
git fetch origin claude/connect-to-api-gWbHB
git checkout -f origin/claude/connect-to-api-gWbHB
docker compose build --no-cache
docker compose up -d
```

Or via the gateway API:
1. Login: `GET /gw/login?username=admin&password=...`
2. Write a deploy script to `/tmp/deploy.sh`
3. Run: `GET /gw/exec?token=...&cmd=systemd-run sh /tmp/deploy.sh`
4. Monitor: `GET /gw/exec?token=...&cmd=tail -5 /tmp/deploy.log`

## Development Notes

- Frontend API calls use relative `/api/` prefix — nginx proxies to backend
- `normalizePath()` in `api.js` adds trailing slashes to prevent FastAPI 307 redirects
- nginx uses `$http_host` (not `$host`) to preserve port in redirect headers
- DB migrations for new columns handled in `database.py:_run_migrations()`
- New tables auto-created by `Base.metadata.create_all()` on startup
- Camera worker auto-derives snapshot URL from RTSP URL if not explicitly set
- Unknown faces saved to `uploads/unknown_faces/` directory
