# MPA Attendance System

School attendance management system using face recognition from Dahua IP cameras.

## Features

- **Face Recognition Attendance** — Automatically records attendance when students are detected by IP cameras
- **HTTP Snapshot Capture** — Grabs JPEG snapshots from Dahua cameras via HTTP (more reliable than RTSP streaming)
- **RTSP Stream Capture** — Alternative real-time video stream processing
- **Manual Attendance** — Check-in/out students manually by student ID
- **Unknown Faces Library** — Captures unidentified faces for manual review and assignment
- **Dashboard** — Today's stats, weekly trends, per-class breakdown
- **Student Management** — CRUD with photo upload and face enrollment
- **Class & Schedule Management** — Define classes, timetables, and holidays
- **Excel Export** — Export attendance records by date range and class
- **Multi-Camera Support** — Entry/exit cameras with per-camera configuration

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI, SQLAlchemy, Uvicorn |
| Frontend | React, Vite, Ant Design |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Face Recognition | InsightFace (buffalo_sc model) |
| Camera Integration | HTTP Snapshots / RTSP via OpenCV |
| Containerization | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Dahua IP camera(s) on the same network

### Deploy

```bash
git clone https://github.com/cinnylane15-debug/mpa-attendance.git
cd mpa-attendance
docker compose up -d --build
```

The app will be available at `http://localhost:3000`.

Default login: `admin` / `Admin@2026`

### Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React SPA (nginx) |
| Backend | 8000 | FastAPI API |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Browser    │────▶│   Frontend   │────▶│   Backend    │
│              │     │  (nginx:80)  │/api/│ (uvicorn:8k) │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    │            │            │
                              ┌─────▼─────┐ ┌───▼───┐ ┌─────▼──────┐
                              │ PostgreSQL │ │ Redis │ │ IP Cameras │
                              │ + pgvector │ │       │ │  (Dahua)   │
                              └───────────┘ └───────┘ └────────────┘
```

## Camera Setup

### Adding a Camera

1. Go to **Cameras** → **Add Camera**
2. Enter the RTSP URL: `rtsp://admin:password@192.168.1.9:554/cam/realmonitor?channel=1&subtype=0`
3. Select **Direction**: Entry or Exit
4. Select **Capture Mode**: HTTP Snapshot (recommended) or RTSP Stream
5. The snapshot URL is auto-derived from the RTSP URL

### Capture Modes

- **HTTP Snapshot** (default): Fetches JPEG images via `http://IP/cgi-bin/snapshot.cgi?channel=N` using HTTP Digest auth. Simple, reliable, no streaming overhead.
- **RTSP Stream**: Continuous video stream via OpenCV/FFmpeg. Lower latency but more complex and prone to connection drops.

## Face Recognition Flow

1. Camera worker captures frame (snapshot or RTSP)
2. InsightFace detects faces and extracts 512-dim embeddings
3. pgvector finds nearest match using cosine similarity
4. If confidence ≥ threshold (40%): record attendance
5. If confidence < threshold: save to **Unknown Faces** library for manual review

## API Documentation

Interactive API docs available at `http://localhost:8000/docs` (Swagger UI).

See [CLAUDE.md](CLAUDE.md) for full endpoint reference.

## Project Structure

```
├── app/                     # FastAPI backend
│   ├── main.py              # App entry, router registration
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── rtsp_worker.py       # Camera capture workers
│   ├── face_engine.py       # InsightFace wrapper
│   └── routers/             # API route handlers
├── frontend/                # React app
│   └── src/pages/           # Page components
├── docker/                  # Dockerfiles + nginx config
└── docker-compose.yml
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PASSWORD` | - | Redis password |
| `SECRET_KEY` | - | JWT signing key |
| `FACE_RECOGNITION_TOLERANCE` | `0.4` | Min similarity for face match (0-1) |
| `INSIGHTFACE_MODEL` | `buffalo_sc` | InsightFace model name |
| `RTSP_FRAME_INTERVAL` | `2.0` | Seconds between frame captures |
| `RTSP_COOLDOWN_MINUTES` | `30` | Min minutes between duplicate attendance |
| `SCHOOL_START_TIME` | `08:00` | School start time (for late detection) |
| `LATE_THRESHOLD_MINUTES` | `15` | Minutes after start to mark as late |

## License

Private project.
