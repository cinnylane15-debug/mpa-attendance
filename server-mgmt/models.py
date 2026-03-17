from pydantic import BaseModel, Field
from datetime import datetime


# --- Auth Models ---

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str
    key_prefix: str
    created_at: str


class ApiKeyListItem(BaseModel):
    id: int
    name: str
    key_prefix: str
    created_at: str
    last_used_at: str | None


# --- System Models ---

class SystemInfo(BaseModel):
    hostname: str
    os: str
    kernel: str
    architecture: str
    cpu_model: str
    cpu_cores: int
    cpu_usage_percent: float
    ram_total_gb: float
    ram_used_gb: float
    ram_usage_percent: float
    disks: list[dict]


class UptimeInfo(BaseModel):
    uptime_seconds: float
    uptime_human: str
    load_avg_1: float
    load_avg_5: float
    load_avg_15: float


class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    username: str


# --- Package Models ---

class PackageAction(BaseModel):
    packages: list[str] = Field(..., min_length=1)


class InstalledPackage(BaseModel):
    name: str
    version: str


# --- Docker Models ---

class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    status: str
    state: str
    ports: str
    created: str


class ImageInfo(BaseModel):
    id: str
    repository: str
    tag: str
    size: str
    created: str


class ImagePullRequest(BaseModel):
    image: str


# --- Deploy Models ---

class StackCreateRequest(BaseModel):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    compose_yaml: str
    env_vars: dict[str, str] = {}


class StackEnvUpdate(BaseModel):
    env_vars: dict[str, str]


class StackInfo(BaseModel):
    name: str
    status: str
    containers: list[ContainerInfo] = []
    created_at: str | None = None


# --- Service Models ---

class ServiceInfo(BaseModel):
    name: str
    load_state: str
    active_state: str
    sub_state: str
    description: str


class ServiceDetail(BaseModel):
    name: str
    load_state: str
    active_state: str
    sub_state: str
    description: str
    main_pid: int
    memory: str
    started_at: str


# --- File Models ---

class FileWriteRequest(BaseModel):
    path: str
    content: str
    mode: str = "0644"


class FileDeleteRequest(BaseModel):
    path: str


class FileEntry(BaseModel):
    name: str
    path: str
    type: str  # file, directory, symlink
    size: int
    modified: str
    permissions: str


# --- Command Models ---

class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1)
    timeout: int = Field(default=120, ge=1, le=600)
    cwd: str | None = None


class CommandResponse(BaseModel):
    returncode: int
    stdout: str
    stderr: str
    success: bool


# --- Network Models ---

class NetworkInterface(BaseModel):
    name: str
    ipv4: list[str]
    ipv6: list[str]
    mac: str
    status: str


class ListeningPort(BaseModel):
    protocol: str
    local_address: str
    port: int
    pid: int | None
    process: str


class PortCheckRequest(BaseModel):
    host: str
    port: int


# --- Audit Models ---

class AuditEntry(BaseModel):
    id: int
    timestamp: str
    user_id: int | None
    action: str
    detail: str | None
    ip_address: str | None
    success: bool


# --- Generic ---

class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    detail: str
    success: bool = False
