#!/usr/bin/env bash
# ============================================================================
# MPA Server Management API — Single-File Installer
# ============================================================================
# Usage: sudo bash install.sh
#
# This script:
#   1. Fixes DNS if broken
#   2. Installs Python3 + pip + venv
#   3. Creates the entire management API from embedded code
#   4. Generates SSL cert, admin password, JWT secret
#   5. Installs as a systemd service on port 8443
#   6. Prints credentials — you're done
#
# After this runs, the API is live at https://<your-ip>:8443
# ============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
INSTALL_DIR="/opt/mpa-mgmt"

echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  MPA Server Management API — One-File Installer   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# --- Must be root ---
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Run as root:  sudo bash install.sh${NC}"
    exit 1
fi

# --- Fix DNS if broken ---
echo -e "${YELLOW}[1/6] Checking network...${NC}"
if ! getent hosts archive.ubuntu.com > /dev/null 2>&1; then
    echo -e "${RED}  DNS broken — fixing...${NC}"
    if systemctl is-active systemd-resolved > /dev/null 2>&1; then
        mkdir -p /etc/systemd/resolved.conf.d
        printf '[Resolve]\nDNS=8.8.8.8 8.8.4.4 1.1.1.1\n' > /etc/systemd/resolved.conf.d/dns.conf
        systemctl restart systemd-resolved
        sleep 2
    else
        cp /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null || true
        printf 'nameserver 8.8.8.8\nnameserver 8.8.4.4\nnameserver 1.1.1.1\n' > /etc/resolv.conf
    fi
    if getent hosts archive.ubuntu.com > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ DNS fixed${NC}"
    else
        echo -e "${RED}  ✗ DNS still broken. Add to your netplan:${NC}"
        echo -e "      nameservers:"
        echo -e "        addresses: [8.8.8.8, 8.8.4.4]"
        echo -e "    Then: sudo netplan apply"
        exit 1
    fi
else
    echo -e "${GREEN}  ✓ Network OK${NC}"
fi

# --- Install system deps ---
echo -e "${YELLOW}[2/6] Installing system packages...${NC}"
if command -v python3 &>/dev/null && python3 -c "import venv" 2>/dev/null && command -v openssl &>/dev/null && command -v pip3 &>/dev/null; then
    echo -e "${GREEN}  ✓ Already installed${NC}"
else
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip python3-venv openssl > /dev/null 2>&1
    echo -e "${GREEN}  ✓ Installed${NC}"
fi

# --- Create project dir + venv ---
echo -e "${YELLOW}[3/6] Setting up Python environment...${NC}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet fastapi==0.115.6 "uvicorn[standard]==0.34.0" pydantic-settings==2.7.1 "python-jose[cryptography]==3.3.0" "bcrypt>=4.0.0" aiosqlite==0.20.0 psutil==6.1.1 python-multipart==0.0.20 cffi
echo -e "${GREEN}  ✓ Python packages installed${NC}"

# --- Generate SSL + secrets ---
echo -e "${YELLOW}[4/6] Generating SSL cert and secrets...${NC}"
if [ ! -f cert.pem ]; then
    openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem \
        -days 365 -nodes -subj "/CN=$(hostname)" 2>/dev/null
fi
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 20)
JWT_SECRET=$(openssl rand -hex 32)

cat > .env <<ENVEOF
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASS}
JWT_SECRET=${JWT_SECRET}
API_PORT=8443
SSL_CERT=${INSTALL_DIR}/cert.pem
SSL_KEY=${INSTALL_DIR}/key.pem
DB_PATH=${INSTALL_DIR}/mgmt.db
STACKS_DIR=${INSTALL_DIR}/stacks
RATE_LIMIT=100
ENVEOF
echo -e "${GREEN}  ✓ SSL cert + secrets generated${NC}"

# --- Write ALL Python source files ---
echo -e "${YELLOW}[5/6] Writing API source code...${NC}"
mkdir -p routers utils stacks

# --- config.py ---
cat > config.py <<'PYEOF'
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    admin_username: str = "admin"
    admin_password: str = "changeme"
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    api_port: int = 8443
    ssl_cert: str = "cert.pem"
    ssl_key: str = "key.pem"
    db_path: str = "mgmt.db"
    stacks_dir: str = "stacks"
    allowed_ips: str = ""
    rate_limit: int = 100
    @property
    def stacks_path(self) -> Path:
        return Path(self.stacks_dir)
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
PYEOF

# --- database.py ---
cat > database.py <<'PYEOF'
import aiosqlite
from config import settings
_db = None

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db

async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT DEFAULT 'admin', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, key_hash TEXT NOT NULL, key_prefix TEXT NOT NULL, created_by INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_used_at TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, user_id INTEGER, action TEXT NOT NULL, detail TEXT, ip_address TEXT, success BOOLEAN DEFAULT 1);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
        CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
    """)
    from auth import hash_password
    row = await db.execute_fetchall("SELECT id FROM users WHERE username = ?", (settings.admin_username,))
    if not row:
        pw = hash_password(settings.admin_password)
        await db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (settings.admin_username, pw, "admin"))
        await db.commit()

async def log_audit(action, user_id=None, detail=None, ip_address=None, success=True):
    db = await get_db()
    await db.execute("INSERT INTO audit_log (user_id, action, detail, ip_address, success) VALUES (?, ?, ?, ?, ?)", (user_id, action, detail, ip_address, success))
    await db.commit()
PYEOF

# --- auth.py ---
cat > auth.py <<'PYEOF'
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
import bcrypt as _bcrypt
from jose import JWTError, jwt
from config import settings
from database import get_db

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def hash_password(password):
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(rounds=12)).decode()

def verify_password(password, password_hash):
    return _bcrypt.checkpw(password.encode(), password_hash.encode())

def create_access_token(user_id, username):
    return jwt.encode({"sub": str(user_id), "username": username, "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes), "type": "access"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(user_id):
    return jwt.encode({"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days), "type": "refresh"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token):
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def generate_api_key():
    return f"mgmt_{secrets.token_hex(32)}"

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security), api_key: str | None = Depends(api_key_header)):
    db = await get_db()
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        row = await db.execute_fetchall("SELECT id, username, role FROM users WHERE id = ?", (int(payload["sub"]),))
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return {"id": row[0][0], "username": row[0][1], "role": row[0][2]}
    if api_key:
        rows = await db.execute_fetchall("SELECT id, key_hash, created_by FROM api_keys WHERE key_prefix = ?", (api_key[:12],))
        for row in rows:
            if verify_password(api_key, row[1]):
                await db.execute("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (row[0],))
                await db.commit()
                ur = await db.execute_fetchall("SELECT id, username, role FROM users WHERE id = ?", (row[2],))
                if ur:
                    return {"id": ur[0][0], "username": ur[0][1], "role": ur[0][2]}
    raise HTTPException(status_code=401, detail="Auth required. Provide Bearer token or X-API-Key.", headers={"WWW-Authenticate": "Bearer"})
PYEOF

# --- middleware.py ---
cat > middleware.py <<'PYEOF'
import time, json
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from database import log_audit

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            uid = getattr(request.state, "user", {}).get("id") if hasattr(request.state, "user") else None
            ip = request.client.host if request.client else "unknown"
            try:
                await log_audit(f"{request.method} {request.url.path}", uid, json.dumps({"q": str(request.query_params)}), ip, response.status_code < 400)
            except Exception:
                pass
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute=100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.requests = defaultdict(list)
    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        self.requests[ip] = [t for t in self.requests[ip] if t > now - 60]
        self.requests[ip].append(now)
        if len(self.requests[ip]) > self.rpm:
            return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json")
        return await call_next(request)
PYEOF

# --- utils/__init__.py ---
touch utils/__init__.py

# --- utils/shell.py ---
cat > utils/shell.py <<'PYEOF'
import asyncio, socket
from dataclasses import dataclass

@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str
    @property
    def success(self):
        return self.returncode == 0
    @property
    def output(self):
        return self.stdout if self.success else self.stderr

async def run_command(command, timeout=120, cwd=None, env=None):
    try:
        p = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd, env=env)
        so, se = await asyncio.wait_for(p.communicate(), timeout=timeout)
        return ShellResult(p.returncode or 0, so.decode("utf-8", errors="replace").strip(), se.decode("utf-8", errors="replace").strip())
    except asyncio.TimeoutError:
        p.kill()
        return ShellResult(-1, "", f"Timed out after {timeout}s")
    except Exception as e:
        return ShellResult(-1, "", str(e))

async def check_internet():
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(loop.getaddrinfo("archive.ubuntu.com", 80), timeout=5)
        return True, "OK"
    except Exception:
        return False, "DNS failed — cannot resolve archive.ubuntu.com. Fix /etc/resolv.conf"
PYEOF

# --- routers/__init__.py ---
touch routers/__init__.py

# --- routers/auth_router.py ---
cat > routers/auth_router.py <<'PYEOF'
from fastapi import APIRouter, Depends, HTTPException
from auth import create_access_token, create_refresh_token, decode_token, generate_api_key, get_current_user, hash_password, verify_password
from database import get_db
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginReq(BaseModel):
    username: str
    password: str

class RefreshReq(BaseModel):
    refresh_token: str

class ApiKeyReq(BaseModel):
    name: str = Field(..., min_length=1)

@router.post("/login")
async def login(req: LoginReq):
    db = await get_db()
    rows = await db.execute_fetchall("SELECT id, username, password_hash FROM users WHERE username = ?", (req.username,))
    if not rows or not verify_password(req.password, rows[0][2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(rows[0][0], rows[0][1]), "refresh_token": create_refresh_token(rows[0][0]), "token_type": "bearer"}

@router.post("/token/refresh")
async def refresh(req: RefreshReq):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    db = await get_db()
    rows = await db.execute_fetchall("SELECT id, username FROM users WHERE id = ?", (int(payload["sub"]),))
    if not rows:
        raise HTTPException(status_code=401, detail="User not found")
    return {"access_token": create_access_token(rows[0][0], rows[0][1]), "refresh_token": create_refresh_token(rows[0][0]), "token_type": "bearer"}

@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    db = await get_db()
    rows = await db.execute_fetchall("SELECT id, username, role, created_at FROM users WHERE id = ?", (user["id"],))
    return {"id": rows[0][0], "username": rows[0][1], "role": rows[0][2], "created_at": str(rows[0][3])}

@router.post("/api-keys")
async def create_key(req: ApiKeyReq, user: dict = Depends(get_current_user)):
    raw = generate_api_key()
    db = await get_db()
    c = await db.execute("INSERT INTO api_keys (name, key_hash, key_prefix, created_by) VALUES (?, ?, ?, ?)", (req.name, hash_password(raw), raw[:12], user["id"]))
    await db.commit()
    return {"id": c.lastrowid, "name": req.name, "key": raw, "key_prefix": raw[:12]}

@router.get("/api-keys")
async def list_keys(user: dict = Depends(get_current_user)):
    db = await get_db()
    rows = await db.execute_fetchall("SELECT id, name, key_prefix, created_at, last_used_at FROM api_keys WHERE created_by = ?", (user["id"],))
    return [{"id": r[0], "name": r[1], "key_prefix": r[2], "created_at": str(r[3]), "last_used_at": str(r[4]) if r[4] else None} for r in rows]

@router.delete("/api-keys/{key_id}")
async def delete_key(key_id: int, user: dict = Depends(get_current_user)):
    db = await get_db()
    r = await db.execute("DELETE FROM api_keys WHERE id = ? AND created_by = ?", (key_id, user["id"]))
    await db.commit()
    if r.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Revoked"}
PYEOF

# --- routers/system.py ---
cat > routers/system.py <<'PYEOF'
import platform, time
import psutil
from fastapi import APIRouter, Depends, Query
from auth import get_current_user

router = APIRouter(prefix="/system", tags=["System"])

@router.get("/info")
async def info(user: dict = Depends(get_current_user)):
    mem = psutil.virtual_memory()
    uname = platform.uname()
    disks = []
    for p in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks.append({"device": p.device, "mount": p.mountpoint, "total_gb": round(u.total/(1024**3),2), "used_gb": round(u.used/(1024**3),2), "pct": u.percent})
        except PermissionError:
            pass
    return {"hostname": uname.node, "os": f"{uname.system} {uname.release}", "arch": uname.machine, "cpu_cores": psutil.cpu_count(logical=True), "cpu_pct": psutil.cpu_percent(interval=0.5), "ram_total_gb": round(mem.total/(1024**3),2), "ram_used_gb": round(mem.used/(1024**3),2), "ram_pct": mem.percent, "disks": disks}

@router.get("/uptime")
async def uptime(user: dict = Depends(get_current_user)):
    up = time.time() - psutil.boot_time()
    l1, l5, l15 = psutil.getloadavg()
    d, r = divmod(int(up), 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return {"uptime_seconds": up, "uptime_human": f"{d}d {h}h {m}m", "load_1": round(l1,2), "load_5": round(l5,2), "load_15": round(l15,2)}

@router.get("/processes")
async def procs(limit: int = Query(default=20, ge=1, le=100), user: dict = Depends(get_current_user)):
    ps = []
    for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status","username"]):
        try:
            i = p.info
            ps.append({"pid": i["pid"], "name": i["name"] or "?", "cpu": i["cpu_percent"] or 0, "mem": round(i["memory_percent"] or 0, 2), "status": i["status"] or "?", "user": i["username"] or "?"})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    ps.sort(key=lambda x: x["cpu"], reverse=True)
    return ps[:limit]
PYEOF

# --- routers/network.py ---
cat > routers/network.py <<'PYEOF'
import asyncio, socket
import psutil
from fastapi import APIRouter, Depends, Query
from auth import get_current_user
from utils.shell import run_command

router = APIRouter(prefix="/network", tags=["Network"])

@router.get("/interfaces")
async def interfaces(user: dict = Depends(get_current_user)):
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    result = []
    for iface, al in addrs.items():
        ipv4, mac = [], ""
        for a in al:
            if a.family == socket.AF_INET: ipv4.append(a.address)
            elif a.family == psutil.AF_LINK: mac = a.address
        s = stats.get(iface)
        result.append({"name": iface, "ipv4": ipv4, "mac": mac, "up": s.isup if s else False})
    return result

@router.get("/ports")
async def ports(user: dict = Depends(get_current_user)):
    result, seen = [], set()
    for c in psutil.net_connections(kind="inet"):
        if c.status != "LISTEN": continue
        key = (c.laddr.ip, c.laddr.port)
        if key in seen: continue
        seen.add(key)
        pname = ""
        if c.pid:
            try: pname = psutil.Process(c.pid).name()
            except: pass
        result.append({"addr": c.laddr.ip, "port": c.laddr.port, "pid": c.pid, "process": pname})
    result.sort(key=lambda x: x["port"])
    return result

@router.get("/check-port")
async def check_port(host: str = Query(...), port: int = Query(..., ge=1, le=65535), user: dict = Depends(get_current_user)):
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
        w.close(); await w.wait_closed()
        return {"host": host, "port": port, "reachable": True}
    except:
        return {"host": host, "port": port, "reachable": False}

@router.get("/firewall")
async def fw(user: dict = Depends(get_current_user)):
    r = await run_command("ufw status verbose 2>/dev/null || echo 'ufw not installed'")
    return {"output": r.stdout or r.stderr}
PYEOF

# --- routers/packages.py ---
cat > routers/packages.py <<'PYEOF'
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from auth import get_current_user
from database import log_audit
from utils.shell import run_command, check_internet

router = APIRouter(prefix="/packages", tags=["Packages"])

class PkgReq(BaseModel):
    packages: list[str] = Field(..., min_length=1)

@router.post("/update")
async def apt_update(user: dict = Depends(get_current_user)):
    ok, msg = await check_internet()
    if not ok: return {"message": msg, "success": False}
    r = await run_command("DEBIAN_FRONTEND=noninteractive apt-get update", timeout=300)
    await log_audit("packages.update", user["id"], r.output[:500], success=r.success)
    return {"message": "Updated" if r.success else f"Failed: {r.stderr[:500]}", "success": r.success}

@router.post("/install")
async def install(req: PkgReq, user: dict = Depends(get_current_user)):
    for p in req.packages:
        if not all(c.isalnum() or c in "-.:+" for c in p):
            return {"message": f"Bad package name: {p}", "success": False}
    ok, msg = await check_internet()
    if not ok: return {"message": msg, "success": False}
    r = await run_command(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {' '.join(req.packages)}", timeout=600)
    await log_audit("packages.install", user["id"], f"{req.packages}: {r.output[:300]}", success=r.success)
    return {"message": f"Installed: {req.packages}" if r.success else f"Failed: {r.stderr[:500]}", "success": r.success}

@router.post("/remove")
async def remove(req: PkgReq, user: dict = Depends(get_current_user)):
    r = await run_command(f"DEBIAN_FRONTEND=noninteractive apt-get remove -y {' '.join(req.packages)}", timeout=300)
    await log_audit("packages.remove", user["id"], str(req.packages), success=r.success)
    return {"message": f"Removed" if r.success else f"Failed: {r.stderr[:500]}", "success": r.success}

@router.get("/installed")
async def installed(search: str = Query(default=""), user: dict = Depends(get_current_user)):
    cmd = f"dpkg-query -W -f='${{Package}} ${{Version}}\\n' 2>/dev/null" + (f" | grep -i '{search}'" if search else " | head -500")
    r = await run_command(cmd)
    return [{"name": l.split()[0], "version": l.split()[1]} for l in r.stdout.splitlines() if len(l.split()) >= 2]
PYEOF

# --- routers/services.py ---
cat > routers/services.py <<'PYEOF'
from fastapi import APIRouter, Depends, Query
from auth import get_current_user
from database import log_audit
from utils.shell import run_command

router = APIRouter(prefix="/services", tags=["Services"])

@router.get("")
async def list_svc(filter: str = Query(default=""), user: dict = Depends(get_current_user)):
    cmd = "systemctl list-units --type=service --no-pager --no-legend --plain"
    if filter in ("running","failed"): cmd += f" --state={filter}"
    r = await run_command(cmd)
    svcs = []
    for l in r.stdout.splitlines():
        p = l.split(None, 4)
        if len(p) >= 4:
            svcs.append({"name": p[0].replace(".service",""), "load": p[1], "active": p[2], "sub": p[3], "desc": p[4] if len(p)>4 else ""})
    return svcs

@router.get("/{name}")
async def svc_status(name: str, user: dict = Depends(get_current_user)):
    r = await run_command(f"systemctl show {name}.service --no-pager --property=LoadState,ActiveState,SubState,Description,MainPID,MemoryCurrent,ActiveEnterTimestamp")
    props = {}
    for l in r.stdout.splitlines():
        if "=" in l: k, v = l.split("=", 1); props[k] = v
    return props

@router.post("/{name}/{action}")
async def svc_action(name: str, action: str, user: dict = Depends(get_current_user)):
    if action not in ("start","stop","restart","enable","disable"):
        return {"message": f"Invalid action: {action}", "success": False}
    r = await run_command(f"systemctl {action} {name}.service")
    await log_audit(f"services.{action}", user["id"], f"service={name}", success=r.success)
    return {"message": f"{name} {action}ed" if r.success else f"Failed: {r.stderr}", "success": r.success}

@router.get("/{name}/logs")
async def svc_logs(name: str, lines: int = Query(default=100, ge=1, le=5000), user: dict = Depends(get_current_user)):
    r = await run_command(f"journalctl -u {name}.service --no-pager -n {lines}")
    return {"service": name, "logs": r.stdout}
PYEOF

# --- routers/docker.py ---
cat > routers/docker.py <<'PYEOF'
import json
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from auth import get_current_user
from database import log_audit
from utils.shell import run_command, check_internet

router = APIRouter(prefix="/docker", tags=["Docker"])

class PullReq(BaseModel):
    image: str

@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    inst = await run_command("docker --version")
    daemon = await run_command("docker info --format '{{.ServerVersion}}'")
    comp = await run_command("docker compose version --short 2>/dev/null")
    return {"installed": inst.success, "version": inst.stdout if inst.success else None, "daemon_running": daemon.success, "compose": comp.stdout if comp.success else None}

@router.post("/install")
async def install_docker(user: dict = Depends(get_current_user)):
    ok, msg = await check_internet()
    if not ok: return {"message": f"Cannot install: {msg}", "success": False}
    cmds = "apt-get update && apt-get install -y ca-certificates curl gnupg && install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg && chmod a+r /etc/apt/keyrings/docker.gpg && echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable\" > /etc/apt/sources.list.d/docker.list && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && systemctl enable docker && systemctl start docker"
    r = await run_command(cmds, timeout=600)
    await log_audit("docker.install", user["id"], r.output[:500], success=r.success)
    return {"message": "Docker installed" if r.success else f"Failed: {r.stderr[:500]}", "success": r.success}

@router.get("/containers")
async def containers(all: bool = Query(default=False), user: dict = Depends(get_current_user)):
    flag = "-a" if all else ""
    r = await run_command(f"docker ps {flag} --format '{{{{json .}}}}'")
    out = []
    for l in r.stdout.splitlines():
        try: out.append(json.loads(l))
        except: pass
    return out

@router.post("/containers/{cid}/{action}")
async def container_action(cid: str, action: str, user: dict = Depends(get_current_user)):
    if action not in ("start","stop","restart"): return {"message": "Invalid action", "success": False}
    r = await run_command(f"docker {action} {cid}")
    await log_audit(f"docker.{action}", user["id"], f"container={cid}", success=r.success)
    return {"message": f"{cid} {action}ed" if r.success else r.stderr, "success": r.success}

@router.delete("/containers/{cid}")
async def rm_container(cid: str, force: bool = Query(default=False), user: dict = Depends(get_current_user)):
    r = await run_command(f"docker rm {'-f' if force else ''} {cid}")
    return {"message": f"Removed {cid}" if r.success else r.stderr, "success": r.success}

@router.get("/containers/{cid}/logs")
async def container_logs(cid: str, tail: int = Query(default=100), user: dict = Depends(get_current_user)):
    r = await run_command(f"docker logs --tail {tail} {cid}")
    return {"logs": r.stdout or r.stderr}

@router.get("/images")
async def images(user: dict = Depends(get_current_user)):
    r = await run_command("docker images --format '{{json .}}'")
    out = []
    for l in r.stdout.splitlines():
        try: out.append(json.loads(l))
        except: pass
    return out

@router.post("/images/pull")
async def pull(req: PullReq, user: dict = Depends(get_current_user)):
    r = await run_command(f"docker pull {req.image}", timeout=600)
    await log_audit("docker.pull", user["id"], f"image={req.image}", success=r.success)
    return {"message": f"Pulled {req.image}" if r.success else r.stderr[:500], "success": r.success}

@router.delete("/images/{iid}")
async def rm_image(iid: str, user: dict = Depends(get_current_user)):
    r = await run_command(f"docker rmi {iid}")
    return {"message": f"Removed" if r.success else r.stderr, "success": r.success}
PYEOF

# --- routers/deploy.py ---
cat > routers/deploy.py <<'PYEOF'
import json, shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from auth import get_current_user
from config import settings
from database import log_audit
from utils.shell import run_command

router = APIRouter(prefix="/deploy", tags=["Deploy"])

class StackReq(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    compose_yaml: str
    env_vars: dict[str, str] = {}

class EnvReq(BaseModel):
    env_vars: dict[str, str]

def _sd(name):
    return settings.stacks_path / name

@router.post("/stack")
async def create(req: StackReq, user: dict = Depends(get_current_user)):
    sd = _sd(req.name); sd.mkdir(parents=True, exist_ok=True)
    (sd / "docker-compose.yml").write_text(req.compose_yaml)
    if req.env_vars:
        (sd / ".env").write_text("\n".join(f"{k}={v}" for k, v in req.env_vars.items()) + "\n")
    r = await run_command(f"docker compose -f {sd/'docker-compose.yml'} up -d", cwd=str(sd), timeout=600)
    await log_audit("deploy.create", user["id"], f"stack={req.name}", success=r.success)
    return {"message": f"Stack '{req.name}' deployed" if r.success else f"Failed: {r.stderr[:500]}", "success": r.success}

@router.delete("/stack/{name}")
async def delete(name: str, user: dict = Depends(get_current_user)):
    sd = _sd(name); cp = sd / "docker-compose.yml"
    if not cp.exists(): return {"message": "Not found", "success": False}
    r = await run_command(f"docker compose -f {cp} down -v", cwd=str(sd), timeout=120)
    shutil.rmtree(sd, ignore_errors=True)
    return {"message": f"Stack '{name}' removed", "success": True}

@router.get("/stacks")
async def list_stacks(user: dict = Depends(get_current_user)):
    sp = settings.stacks_path
    if not sp.exists(): return []
    return [{"name": e.name} for e in sorted(sp.iterdir()) if e.is_dir() and (e/"docker-compose.yml").exists()]

@router.post("/stack/{name}/up")
async def up(name: str, user: dict = Depends(get_current_user)):
    cp = _sd(name) / "docker-compose.yml"
    if not cp.exists(): return {"message": "Not found", "success": False}
    r = await run_command(f"docker compose -f {cp} up -d", cwd=str(_sd(name)), timeout=600)
    return {"message": "Up" if r.success else r.stderr[:500], "success": r.success}

@router.post("/stack/{name}/down")
async def down(name: str, user: dict = Depends(get_current_user)):
    cp = _sd(name) / "docker-compose.yml"
    if not cp.exists(): return {"message": "Not found", "success": False}
    r = await run_command(f"docker compose -f {cp} down", cwd=str(_sd(name)), timeout=120)
    return {"message": "Down" if r.success else r.stderr[:500], "success": r.success}

@router.get("/stack/{name}/status")
async def stack_status(name: str, user: dict = Depends(get_current_user)):
    cp = _sd(name) / "docker-compose.yml"
    if not cp.exists(): return {"name": name, "status": "not_found"}
    r = await run_command(f"docker compose -f {cp} ps --format json", cwd=str(_sd(name)))
    containers = []
    if r.success and r.stdout:
        try:
            data = r.stdout
            items = json.loads(data) if data.startswith("[") else [json.loads(l) for l in data.splitlines() if l.strip()]
            containers = items
        except: pass
    return {"name": name, "containers": containers}

@router.post("/stack/{name}/env")
async def update_env(name: str, req: EnvReq, user: dict = Depends(get_current_user)):
    sd = _sd(name)
    if not sd.exists(): return {"message": "Not found", "success": False}
    (sd / ".env").write_text("\n".join(f"{k}={v}" for k, v in req.env_vars.items()) + "\n")
    return {"message": "Env updated. Restart stack to apply.", "success": True}

@router.get("/stack/{name}/logs")
async def logs(name: str, tail: int = Query(default=100), user: dict = Depends(get_current_user)):
    cp = _sd(name) / "docker-compose.yml"
    if not cp.exists(): return {"logs": "", "success": False}
    r = await run_command(f"docker compose -f {cp} logs --tail {tail} --no-color", cwd=str(_sd(name)))
    return {"logs": r.stdout or r.stderr, "success": r.success}
PYEOF

# --- routers/files.py ---
cat > routers/files.py <<'PYEOF'
import os, stat, shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auth import get_current_user
from database import log_audit

router = APIRouter(prefix="/files", tags=["Files"])

class WriteReq(BaseModel):
    path: str
    content: str
    mode: str = "0644"

class DelReq(BaseModel):
    path: str

@router.get("/list")
async def ls(path: str = Query(default="/"), user: dict = Depends(get_current_user)):
    p = Path(path).resolve()
    if not p.is_dir(): return []
    entries = []
    try:
        for e in sorted(p.iterdir()):
            try:
                s = e.lstat()
                entries.append({"name": e.name, "path": str(e), "type": "dir" if e.is_dir() else "file", "size": s.st_size, "modified": datetime.fromtimestamp(s.st_mtime).isoformat()})
            except: pass
    except PermissionError: pass
    return entries

@router.get("/read")
async def read(path: str = Query(...), user: dict = Depends(get_current_user)):
    p = Path(path).resolve()
    if not p.is_file(): return {"content": "", "error": "Not found", "success": False}
    if p.stat().st_size > 1048576: return {"content": "", "error": "Too large", "success": False}
    return {"content": p.read_text(errors="replace"), "success": True}

@router.post("/write")
async def write(req: WriteReq, user: dict = Depends(get_current_user)):
    p = Path(req.path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(req.content)
    try: os.chmod(str(p), int(req.mode, 8))
    except: pass
    await log_audit("files.write", user["id"], f"path={req.path}")
    return {"message": f"Written: {req.path}", "success": True}

@router.post("/upload")
async def upload(path: str = Query(...), file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    p = Path(path).resolve(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(await file.read())
    await log_audit("files.upload", user["id"], f"path={path}")
    return {"message": f"Uploaded to {path}", "success": True}

@router.get("/download")
async def download(path: str = Query(...), user: dict = Depends(get_current_user)):
    p = Path(path).resolve()
    if not p.is_file(): return {"message": "Not found", "success": False}
    return FileResponse(str(p), filename=p.name)

@router.delete("/delete")
async def delete(req: DelReq, user: dict = Depends(get_current_user)):
    p = Path(req.path).resolve()
    if not p.exists(): return {"message": "Not found", "success": False}
    if p.is_dir(): shutil.rmtree(str(p))
    else: p.unlink()
    await log_audit("files.delete", user["id"], f"path={req.path}")
    return {"message": f"Deleted: {req.path}", "success": True}
PYEOF

# --- routers/commands.py ---
cat > routers/commands.py <<'PYEOF'
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from auth import get_current_user
from database import log_audit
from utils.shell import run_command

router = APIRouter(prefix="/commands", tags=["Commands"])

class CmdReq(BaseModel):
    command: str = Field(..., min_length=1)
    timeout: int = Field(default=120, ge=1, le=600)
    cwd: str | None = None

@router.post("/execute")
async def execute(req: CmdReq, user: dict = Depends(get_current_user)):
    r = await run_command(req.command, timeout=req.timeout, cwd=req.cwd)
    await log_audit("commands.execute", user["id"], f"cmd={req.command[:200]}", success=r.success)
    return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "success": r.success}
PYEOF

# --- main.py ---
cat > main.py <<'PYEOF'
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user
from config import settings
from database import close_db, get_db, init_db
from middleware import AuditMiddleware, RateLimitMiddleware
from routers import auth_router, commands, deploy, docker, files, network, packages, services, system

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    Path(settings.stacks_dir).mkdir(parents=True, exist_ok=True)
    print(f"Management API started on port {settings.api_port}")
    yield
    await close_db()

app = FastAPI(title="MPA Server Management API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit)
app.add_middleware(AuditMiddleware)

for r in [auth_router, system, packages, docker, deploy, services, files, commands, network]:
    app.include_router(r.router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "mpa-server-mgmt"}

@app.get("/audit/log", tags=["Audit"])
async def audit_log(limit: int = 50, action: str | None = None, user: dict = Depends(get_current_user)):
    db = await get_db()
    if action:
        rows = await db.execute_fetchall("SELECT id, timestamp, user_id, action, detail, ip_address, success FROM audit_log WHERE action LIKE ? ORDER BY timestamp DESC LIMIT ?", (f"%{action}%", limit))
    else:
        rows = await db.execute_fetchall("SELECT id, timestamp, user_id, action, detail, ip_address, success FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,))
    return [{"id": r[0], "timestamp": str(r[1]), "user_id": r[2], "action": r[3], "detail": r[4], "ip": r[5], "success": bool(r[6])} for r in rows]

if __name__ == "__main__":
    import uvicorn
    sc = settings.ssl_cert if Path(settings.ssl_cert).exists() else None
    sk = settings.ssl_key if Path(settings.ssl_key).exists() else None
    uvicorn.run("main:app", host="0.0.0.0", port=settings.api_port, ssl_certfile=sc, ssl_keyfile=sk)
PYEOF

echo -e "${GREEN}  ✓ All source files written${NC}"

# --- Init DB + systemd service ---
echo -e "${YELLOW}[6/6] Starting service...${NC}"
source venv/bin/activate
python3 -c "import asyncio; import sys; sys.path.insert(0,'.'); from database import init_db; asyncio.run(init_db())"

cat > /etc/systemd/system/mpa-mgmt.service <<SVCEOF
[Unit]
Description=MPA Server Management API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-certfile cert.pem --ssl-keyfile key.pem
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable mpa-mgmt.service
systemctl restart mpa-mgmt.service

sleep 2
if systemctl is-active mpa-mgmt.service > /dev/null 2>&1; then
    STATUS="${GREEN}RUNNING${NC}"
else
    STATUS="${RED}FAILED — check: journalctl -u mpa-mgmt -n 50${NC}"
fi

SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              SETUP COMPLETE!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Status:  ${STATUS}"
echo -e "  API:     ${YELLOW}https://${SERVER_IP}:8443${NC}"
echo -e "  Docs:    ${YELLOW}https://${SERVER_IP}:8443/docs${NC}"
echo -e "  Health:  ${YELLOW}https://${SERVER_IP}:8443/health${NC}"
echo ""
echo -e "  ${RED}┌──────────────────────────────────────────┐${NC}"
echo -e "  ${RED}│  SAVE THESE — SHOWN ONCE ONLY            │${NC}"
echo -e "  ${RED}│                                          │${NC}"
echo -e "  ${RED}│  Username: admin                         │${NC}"
echo -e "  ${RED}│  Password: ${ADMIN_PASS}$(printf '%*s' $((19 - ${#ADMIN_PASS})) '')│${NC}"
echo -e "  ${RED}└──────────────────────────────────────────┘${NC}"
echo ""
echo -e "  Commands:"
echo -e "    systemctl status mpa-mgmt"
echo -e "    journalctl -u mpa-mgmt -f"
echo ""
