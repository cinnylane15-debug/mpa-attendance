from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from database import log_audit
from models import MessageResponse, ServiceDetail, ServiceInfo
from utils.shell import run_command

router = APIRouter(prefix="/services", tags=["Service Management"])


@router.get("", response_model=list[ServiceInfo])
async def list_services(
    filter: str = Query(default="", description="Filter: running, failed, enabled, or empty for all"),
    user: dict = Depends(get_current_user),
):
    cmd = "systemctl list-units --type=service --no-pager --no-legend --plain"
    if filter == "running":
        cmd += " --state=running"
    elif filter == "failed":
        cmd += " --state=failed"

    result = await run_command(cmd)
    services = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            name = parts[0].replace(".service", "")
            services.append(ServiceInfo(
                name=name,
                load_state=parts[1],
                active_state=parts[2],
                sub_state=parts[3],
                description=parts[4] if len(parts) > 4 else "",
            ))
    return services


@router.get("/{name}", response_model=ServiceDetail)
async def service_status(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl show {name}.service --no-pager --property=LoadState,ActiveState,SubState,Description,MainPID,MemoryCurrent,ActiveEnterTimestamp")
    props = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v

    mem_bytes = int(props.get("MemoryCurrent", "0") or "0")
    mem_str = f"{mem_bytes / (1024*1024):.1f} MB" if mem_bytes > 0 else "N/A"

    return ServiceDetail(
        name=name,
        load_state=props.get("LoadState", "unknown"),
        active_state=props.get("ActiveState", "unknown"),
        sub_state=props.get("SubState", "unknown"),
        description=props.get("Description", ""),
        main_pid=int(props.get("MainPID", "0") or "0"),
        memory=mem_str,
        started_at=props.get("ActiveEnterTimestamp", ""),
    )


@router.post("/{name}/start", response_model=MessageResponse)
async def start_service(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl start {name}.service")
    await log_audit("services.start", user["id"], f"service={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed to start {name}: {result.stderr}", success=False)
    return MessageResponse(message=f"Service {name} started")


@router.post("/{name}/stop", response_model=MessageResponse)
async def stop_service(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl stop {name}.service")
    await log_audit("services.stop", user["id"], f"service={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed to stop {name}: {result.stderr}", success=False)
    return MessageResponse(message=f"Service {name} stopped")


@router.post("/{name}/restart", response_model=MessageResponse)
async def restart_service(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl restart {name}.service")
    await log_audit("services.restart", user["id"], f"service={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed to restart {name}: {result.stderr}", success=False)
    return MessageResponse(message=f"Service {name} restarted")


@router.post("/{name}/enable", response_model=MessageResponse)
async def enable_service(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl enable {name}.service")
    await log_audit("services.enable", user["id"], f"service={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed to enable {name}: {result.stderr}", success=False)
    return MessageResponse(message=f"Service {name} enabled")


@router.post("/{name}/disable", response_model=MessageResponse)
async def disable_service(name: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"systemctl disable {name}.service")
    await log_audit("services.disable", user["id"], f"service={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed to disable {name}: {result.stderr}", success=False)
    return MessageResponse(message=f"Service {name} disabled")


@router.get("/{name}/logs")
async def service_logs(
    name: str,
    lines: int = Query(default=100, ge=1, le=5000),
    user: dict = Depends(get_current_user),
):
    result = await run_command(f"journalctl -u {name}.service --no-pager -n {lines}")
    return {"service": name, "logs": result.stdout, "success": result.success}
