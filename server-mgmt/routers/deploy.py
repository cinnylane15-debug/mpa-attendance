import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from config import settings
from database import log_audit
from models import (
    ContainerInfo,
    MessageResponse,
    StackCreateRequest,
    StackEnvUpdate,
    StackInfo,
)
from utils.shell import run_command

router = APIRouter(prefix="/deploy", tags=["Stack Deployment"])


def _stack_dir(name: str) -> Path:
    return settings.stacks_path / name


def _validate_stack_name(name: str) -> bool:
    """Prevent path traversal."""
    return name.isidentifier() or all(c.isalnum() or c in "-_" for c in name)


@router.post("/stack", response_model=MessageResponse)
async def create_stack(req: StackCreateRequest, user: dict = Depends(get_current_user)):
    if not _validate_stack_name(req.name):
        return MessageResponse(message="Invalid stack name", success=False)

    stack_dir = _stack_dir(req.name)
    stack_dir.mkdir(parents=True, exist_ok=True)

    # Write docker-compose.yml
    compose_path = stack_dir / "docker-compose.yml"
    compose_path.write_text(req.compose_yaml)

    # Write .env if provided
    if req.env_vars:
        env_path = stack_dir / ".env"
        env_content = "\n".join(f"{k}={v}" for k, v in req.env_vars.items())
        env_path.write_text(env_content + "\n")

    # docker compose up
    result = await run_command(
        f"docker compose -f {compose_path} up -d",
        cwd=str(stack_dir),
        timeout=600,
    )
    await log_audit(
        "deploy.stack.create",
        user["id"],
        f"stack={req.name}, result={result.output[:500]}",
        success=result.success,
    )

    if not result.success:
        return MessageResponse(message=f"Deploy failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Stack '{req.name}' deployed successfully")


@router.delete("/stack/{name}", response_model=MessageResponse)
async def delete_stack(name: str, user: dict = Depends(get_current_user)):
    stack_dir = _stack_dir(name)
    compose_path = stack_dir / "docker-compose.yml"

    if not compose_path.exists():
        return MessageResponse(message=f"Stack '{name}' not found", success=False)

    # docker compose down
    result = await run_command(
        f"docker compose -f {compose_path} down -v",
        cwd=str(stack_dir),
        timeout=120,
    )
    await log_audit("deploy.stack.delete", user["id"], f"stack={name}", success=result.success)

    # Remove stack directory
    import shutil
    shutil.rmtree(stack_dir, ignore_errors=True)

    if not result.success:
        return MessageResponse(message=f"Teardown had errors: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Stack '{name}' removed")


@router.get("/stacks", response_model=list[StackInfo])
async def list_stacks(user: dict = Depends(get_current_user)):
    stacks_dir = settings.stacks_path
    if not stacks_dir.exists():
        return []

    result = []
    for entry in sorted(stacks_dir.iterdir()):
        if entry.is_dir() and (entry / "docker-compose.yml").exists():
            # Get container status
            ps_result = await run_command(
                f"docker compose -f {entry / 'docker-compose.yml'} ps --format json 2>/dev/null",
                cwd=str(entry),
            )
            containers = []
            status = "unknown"
            if ps_result.success and ps_result.stdout:
                try:
                    # docker compose ps --format json can return array or newline-separated objects
                    data = ps_result.stdout
                    if data.startswith("["):
                        items = json.loads(data)
                    else:
                        items = [json.loads(line) for line in data.splitlines() if line.strip()]

                    for item in items:
                        containers.append(ContainerInfo(
                            id=item.get("ID", ""),
                            name=item.get("Name", ""),
                            image=item.get("Image", ""),
                            status=item.get("Status", ""),
                            state=item.get("State", ""),
                            ports=str(item.get("Ports", "")),
                            created=item.get("CreatedAt", ""),
                        ))

                    if containers:
                        states = [c.state for c in containers]
                        if all(s == "running" for s in states):
                            status = "running"
                        elif any(s == "running" for s in states):
                            status = "partial"
                        else:
                            status = "stopped"
                except (json.JSONDecodeError, KeyError):
                    status = "error"
            else:
                status = "stopped"

            stat = entry.stat()
            result.append(StackInfo(
                name=entry.name,
                status=status,
                containers=containers,
                created_at=str(stat.st_ctime),
            ))

    return result


@router.post("/stack/{name}/up", response_model=MessageResponse)
async def stack_up(name: str, user: dict = Depends(get_current_user)):
    compose_path = _stack_dir(name) / "docker-compose.yml"
    if not compose_path.exists():
        return MessageResponse(message=f"Stack '{name}' not found", success=False)

    result = await run_command(
        f"docker compose -f {compose_path} up -d",
        cwd=str(_stack_dir(name)),
        timeout=600,
    )
    await log_audit("deploy.stack.up", user["id"], f"stack={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Stack '{name}' is up")


@router.post("/stack/{name}/down", response_model=MessageResponse)
async def stack_down(name: str, user: dict = Depends(get_current_user)):
    compose_path = _stack_dir(name) / "docker-compose.yml"
    if not compose_path.exists():
        return MessageResponse(message=f"Stack '{name}' not found", success=False)

    result = await run_command(
        f"docker compose -f {compose_path} down",
        cwd=str(_stack_dir(name)),
        timeout=120,
    )
    await log_audit("deploy.stack.down", user["id"], f"stack={name}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Stack '{name}' is down")


@router.get("/stack/{name}/status", response_model=StackInfo)
async def stack_status(name: str, user: dict = Depends(get_current_user)):
    stack_dir = _stack_dir(name)
    compose_path = stack_dir / "docker-compose.yml"
    if not compose_path.exists():
        return StackInfo(name=name, status="not_found")

    ps_result = await run_command(
        f"docker compose -f {compose_path} ps --format json 2>/dev/null",
        cwd=str(stack_dir),
    )
    containers = []
    status = "stopped"
    if ps_result.success and ps_result.stdout:
        try:
            data = ps_result.stdout
            if data.startswith("["):
                items = json.loads(data)
            else:
                items = [json.loads(line) for line in data.splitlines() if line.strip()]

            for item in items:
                containers.append(ContainerInfo(
                    id=item.get("ID", ""),
                    name=item.get("Name", ""),
                    image=item.get("Image", ""),
                    status=item.get("Status", ""),
                    state=item.get("State", ""),
                    ports=str(item.get("Ports", "")),
                    created=item.get("CreatedAt", ""),
                ))

            states = [c.state for c in containers]
            if all(s == "running" for s in states):
                status = "running"
            elif any(s == "running" for s in states):
                status = "partial"
        except (json.JSONDecodeError, KeyError):
            status = "error"

    return StackInfo(name=name, status=status, containers=containers)


@router.post("/stack/{name}/env", response_model=MessageResponse)
async def update_stack_env(
    name: str, req: StackEnvUpdate, user: dict = Depends(get_current_user)
):
    stack_dir = _stack_dir(name)
    if not stack_dir.exists():
        return MessageResponse(message=f"Stack '{name}' not found", success=False)

    env_path = stack_dir / ".env"
    env_content = "\n".join(f"{k}={v}" for k, v in req.env_vars.items())
    env_path.write_text(env_content + "\n")

    await log_audit("deploy.stack.env_update", user["id"], f"stack={name}")
    return MessageResponse(message=f"Environment updated for stack '{name}'. Restart the stack to apply.")


@router.get("/stack/{name}/logs")
async def stack_logs(
    name: str,
    tail: int = Query(default=100, ge=1, le=5000),
    user: dict = Depends(get_current_user),
):
    compose_path = _stack_dir(name) / "docker-compose.yml"
    if not compose_path.exists():
        return {"stack": name, "logs": "", "success": False}

    result = await run_command(
        f"docker compose -f {compose_path} logs --tail {tail} --no-color",
        cwd=str(_stack_dir(name)),
    )
    return {"stack": name, "logs": result.stdout or result.stderr, "success": result.success}
