import platform

import psutil
from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from models import ProcessInfo, SystemInfo, UptimeInfo

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/info", response_model=SystemInfo)
async def system_info(user: dict = Depends(get_current_user)):
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "usage_percent": usage.percent,
            })
        except PermissionError:
            continue

    uname = platform.uname()
    return SystemInfo(
        hostname=uname.node,
        os=f"{uname.system} {uname.release}",
        kernel=uname.release,
        architecture=uname.machine,
        cpu_model=uname.processor or "unknown",
        cpu_cores=psutil.cpu_count(logical=True) or 0,
        cpu_usage_percent=psutil.cpu_percent(interval=0.5),
        ram_total_gb=round(mem.total / (1024**3), 2),
        ram_used_gb=round(mem.used / (1024**3), 2),
        ram_usage_percent=mem.percent,
        disks=disks,
    )


@router.get("/uptime", response_model=UptimeInfo)
async def system_uptime(user: dict = Depends(get_current_user)):
    import time

    boot_time = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    load1, load5, load15 = psutil.getloadavg()

    # Human-readable uptime
    days = int(uptime_secs // 86400)
    hours = int((uptime_secs % 86400) // 3600)
    minutes = int((uptime_secs % 3600) // 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return UptimeInfo(
        uptime_seconds=uptime_secs,
        uptime_human=" ".join(parts),
        load_avg_1=round(load1, 2),
        load_avg_5=round(load5, 2),
        load_avg_15=round(load15, 2),
    )


@router.get("/processes", response_model=list[ProcessInfo])
async def system_processes(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "username"]):
        try:
            info = proc.info
            procs.append(ProcessInfo(
                pid=info["pid"],
                name=info["name"] or "unknown",
                cpu_percent=info["cpu_percent"] or 0.0,
                memory_percent=round(info["memory_percent"] or 0.0, 2),
                status=info["status"] or "unknown",
                username=info["username"] or "unknown",
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda p: p.cpu_percent, reverse=True)
    return procs[:limit]
