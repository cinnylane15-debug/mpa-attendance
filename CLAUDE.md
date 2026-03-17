# MPA Attendance Project

## Server Management API

- **Base URL**: `https://mpa.osetec.net`
- **Access Method**: Use `WebFetch` tool (curl does not work from this environment due to proxy restrictions)
- **Auth**: JWT Bearer token or X-API-Key header

### Credentials

- Username: `admin`
- Password: `vdIwqkLoeMNhF4TP7Lwq`

### Authentication Flow

1. **Login** — `POST /auth/login` with `{"username": "admin", "password": "vdIwqkLoeMNhF4TP7Lwq"}`
2. Returns `access_token` and `refresh_token`
3. Use `Authorization: Bearer <access_token>` on all subsequent requests
4. **Refresh** — `POST /auth/token/refresh` with `{"refresh_token": "..."}`

### API Endpoints

All endpoints (except `/health` and `/auth/login`) require authentication.

#### Health
- `GET /health` — no auth needed

#### Auth (`/auth`)
- `POST /auth/login` — login, returns tokens
- `POST /auth/token/refresh` — refresh access token
- `GET /auth/me` — current user info
- `POST /auth/api-keys` — create API key `{"name": "..."}`
- `GET /auth/api-keys` — list API keys
- `DELETE /auth/api-keys/{key_id}` — revoke key

#### System (`/system`)
- `GET /system/info` — CPU, RAM, disk, hostname, OS
- `GET /system/uptime` — uptime and load averages
- `GET /system/processes?limit=20` — top processes by CPU

#### Packages (`/packages`)
- `POST /packages/update` — apt-get update
- `POST /packages/install` — `{"packages": ["pkg1", "pkg2"]}`
- `POST /packages/remove` — `{"packages": ["pkg1"]}`
- `GET /packages/installed?search=` — list installed packages

#### Docker (`/docker`)
- `GET /docker/status` — Docker installation/daemon status
- `POST /docker/install` — install Docker
- `GET /docker/containers?all=false` — list containers
- `POST /docker/containers/{cid}/{action}` — start/stop/restart
- `DELETE /docker/containers/{cid}?force=false` — remove container
- `GET /docker/containers/{cid}/logs?tail=100` — container logs
- `GET /docker/images` — list images
- `POST /docker/images/pull` — `{"image": "nginx:latest"}`
- `DELETE /docker/images/{iid}` — remove image

#### Deploy (`/deploy`)
- `POST /deploy/stack` — `{"name": "myapp", "compose_yaml": "...", "env_vars": {}}`
- `DELETE /deploy/stack/{name}` — tear down and remove stack
- `GET /deploy/stacks` — list all stacks
- `POST /deploy/stack/{name}/up` — start stack
- `POST /deploy/stack/{name}/down` — stop stack
- `GET /deploy/stack/{name}/status` — stack container status
- `POST /deploy/stack/{name}/env` — `{"env_vars": {"KEY": "VAL"}}`
- `GET /deploy/stack/{name}/logs?tail=100` — stack logs

#### Services (`/services`)
- `GET /services?filter=` — list systemd services (filter: running, failed)
- `GET /services/{name}` — service details
- `POST /services/{name}/{action}` — start/stop/restart/enable/disable
- `GET /services/{name}/logs?lines=100` — journalctl logs

#### Files (`/files`)
- `GET /files/list?path=/` — list directory
- `GET /files/read?path=...` — read file content
- `POST /files/write` — `{"path": "...", "content": "...", "mode": "0644"}`
- `POST /files/upload?path=...` — multipart file upload
- `GET /files/download?path=...` — download file
- `DELETE /files/delete` — `{"path": "..."}`

#### Commands (`/commands`)
- `POST /commands/execute` — `{"command": "...", "timeout": 120, "cwd": null}`

#### Network (`/network`)
- `GET /network/interfaces` — list network interfaces
- `GET /network/ports` — list listening ports
- `GET /network/check-port?host=...&port=...` — check port reachability
- `GET /network/firewall` — UFW status

#### Audit (`/audit`)
- `GET /audit/log?limit=50&action=` — view audit log

#### Gateway (`/gw`) — GET-based endpoints for proxy-restricted environments

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

### Server Details

- Server IP: `72.255.61.75`
- API runs on port `4433` locally with self-signed SSL
- Exposed via Cloudflare Tunnel (tunnel ID: `54ea2776-579b-42f4-976e-50519a7715f0`)
- Installed at `/opt/mpa-mgmt` on the server
- Systemd service: `mpa-mgmt`

### Installed Infrastructure

- **Docker** v29.3.0 + Docker Compose v5.1.0
- **Nginx** v1.24.0 — reverse proxy on port 80 → app on port 8000
- **PostgreSQL 16** — Docker container `mpa-postgres`, port 5432
  - Database: `mpa_attendance`
  - User: `mpa_admin` / Password: `MpaSecure2026x`
- **Redis 7** — Docker container `mpa-redis`, port 6379
  - Password: `MpaRedis2026x`
- **Python venv** at `/opt/mpa-app/venv`
  - FastAPI, Uvicorn, SQLAlchemy, Alembic
  - face_recognition, dlib, OpenCV
  - psycopg2-binary, redis, bcrypt, python-jose, httpx, Pillow
