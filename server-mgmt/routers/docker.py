import json

from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from database import log_audit
from models import ContainerInfo, ImageInfo, ImagePullRequest, MessageResponse
from utils.shell import run_command

router = APIRouter(prefix="/docker", tags=["Docker Management"])


@router.get("/status")
async def docker_status(user: dict = Depends(get_current_user)):
    installed = await run_command("docker --version")
    daemon = await run_command("docker info --format '{{.ServerVersion}}'")
    compose = await run_command("docker compose version --short 2>/dev/null || docker-compose --version 2>/dev/null")
    return {
        "installed": installed.success,
        "version": installed.stdout if installed.success else None,
        "daemon_running": daemon.success,
        "daemon_version": daemon.stdout if daemon.success else None,
        "compose_installed": compose.success,
        "compose_version": compose.stdout if compose.success else None,
    }


@router.post("/install", response_model=MessageResponse)
async def install_docker(user: dict = Depends(get_current_user)):
    # Install Docker using the official convenience script
    commands = [
        "apt-get update",
        "apt-get install -y ca-certificates curl gnupg",
        "install -m 0755 -d /etc/apt/keyrings",
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg",
        "chmod a+r /etc/apt/keyrings/docker.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list',
        "apt-get update",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        "systemctl enable docker",
        "systemctl start docker",
    ]

    full_cmd = " && ".join(commands)
    result = await run_command(full_cmd, timeout=600)
    await log_audit("docker.install", user["id"], result.output[:500], success=result.success)

    if not result.success:
        return MessageResponse(message=f"Docker install failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message="Docker installed and started successfully")


@router.get("/containers", response_model=list[ContainerInfo])
async def list_containers(
    all: bool = Query(default=False, description="Include stopped containers"),
    user: dict = Depends(get_current_user),
):
    flag = "-a" if all else ""
    result = await run_command(
        f"docker ps {flag} --format '{{{{json .}}}}'"
    )
    containers = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            containers.append(ContainerInfo(
                id=data.get("ID", ""),
                name=data.get("Names", ""),
                image=data.get("Image", ""),
                status=data.get("Status", ""),
                state=data.get("State", ""),
                ports=data.get("Ports", ""),
                created=data.get("CreatedAt", ""),
            ))
        except json.JSONDecodeError:
            continue
    return containers


@router.post("/containers/{container_id}/start", response_model=MessageResponse)
async def start_container(container_id: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"docker start {container_id}")
    await log_audit("docker.container.start", user["id"], f"container={container_id}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr}", success=False)
    return MessageResponse(message=f"Container {container_id} started")


@router.post("/containers/{container_id}/stop", response_model=MessageResponse)
async def stop_container(container_id: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"docker stop {container_id}")
    await log_audit("docker.container.stop", user["id"], f"container={container_id}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr}", success=False)
    return MessageResponse(message=f"Container {container_id} stopped")


@router.post("/containers/{container_id}/restart", response_model=MessageResponse)
async def restart_container(container_id: str, user: dict = Depends(get_current_user)):
    result = await run_command(f"docker restart {container_id}")
    await log_audit("docker.container.restart", user["id"], f"container={container_id}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr}", success=False)
    return MessageResponse(message=f"Container {container_id} restarted")


@router.delete("/containers/{container_id}", response_model=MessageResponse)
async def remove_container(
    container_id: str,
    force: bool = Query(default=False),
    user: dict = Depends(get_current_user),
):
    flag = "-f" if force else ""
    result = await run_command(f"docker rm {flag} {container_id}")
    await log_audit("docker.container.remove", user["id"], f"container={container_id}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr}", success=False)
    return MessageResponse(message=f"Container {container_id} removed")


@router.get("/containers/{container_id}/logs")
async def container_logs(
    container_id: str,
    tail: int = Query(default=100, ge=1, le=5000),
    user: dict = Depends(get_current_user),
):
    result = await run_command(f"docker logs --tail {tail} {container_id}")
    return {
        "container_id": container_id,
        "logs": result.stdout or result.stderr,
        "success": result.success,
    }


@router.get("/images", response_model=list[ImageInfo])
async def list_images(user: dict = Depends(get_current_user)):
    result = await run_command("docker images --format '{{json .}}'")
    images = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            images.append(ImageInfo(
                id=data.get("ID", ""),
                repository=data.get("Repository", ""),
                tag=data.get("Tag", ""),
                size=data.get("Size", ""),
                created=data.get("CreatedSince", ""),
            ))
        except json.JSONDecodeError:
            continue
    return images


@router.post("/images/pull", response_model=MessageResponse)
async def pull_image(req: ImagePullRequest, user: dict = Depends(get_current_user)):
    result = await run_command(f"docker pull {req.image}", timeout=600)
    await log_audit("docker.image.pull", user["id"], f"image={req.image}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Pull failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Image {req.image} pulled successfully")


@router.delete("/images/{image_id}", response_model=MessageResponse)
async def remove_image(
    image_id: str,
    force: bool = Query(default=False),
    user: dict = Depends(get_current_user),
):
    flag = "-f" if force else ""
    result = await run_command(f"docker rmi {flag} {image_id}")
    await log_audit("docker.image.remove", user["id"], f"image={image_id}", success=result.success)
    if not result.success:
        return MessageResponse(message=f"Failed: {result.stderr}", success=False)
    return MessageResponse(message=f"Image {image_id} removed")
