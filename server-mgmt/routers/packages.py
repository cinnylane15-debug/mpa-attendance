from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from database import log_audit
from models import InstalledPackage, MessageResponse, PackageAction
from utils.shell import check_internet, run_command, run_command_list

router = APIRouter(prefix="/packages", tags=["Package Management"])


@router.post("/update", response_model=MessageResponse)
async def apt_update(user: dict = Depends(get_current_user)):
    ok, msg = await check_internet()
    if not ok:
        return MessageResponse(message=msg, success=False)
    result = await run_command("DEBIAN_FRONTEND=noninteractive apt-get update", timeout=300)
    await log_audit("packages.update", user["id"], result.output, success=result.success)
    if not result.success:
        return MessageResponse(message=f"apt update failed: {result.stderr}", success=False)
    return MessageResponse(message="Package lists updated")


@router.post("/install", response_model=MessageResponse)
async def install_packages(req: PackageAction, user: dict = Depends(get_current_user)):
    # Validate package names (alphanumeric, hyphens, dots, colons, plus signs)
    for pkg in req.packages:
        if not all(c.isalnum() or c in "-.:+" for c in pkg):
            return MessageResponse(message=f"Invalid package name: {pkg}", success=False)

    ok, msg = await check_internet()
    if not ok:
        return MessageResponse(message=msg, success=False)

    packages_str = " ".join(req.packages)
    cmd = f"DEBIAN_FRONTEND=noninteractive apt-get install -y {packages_str}"
    result = await run_command(cmd, timeout=600)
    await log_audit(
        "packages.install",
        user["id"],
        f"packages={packages_str}, result={result.output[:500]}",
        success=result.success,
    )
    if not result.success:
        return MessageResponse(message=f"Install failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Installed: {packages_str}")


@router.post("/remove", response_model=MessageResponse)
async def remove_packages(req: PackageAction, user: dict = Depends(get_current_user)):
    for pkg in req.packages:
        if not all(c.isalnum() or c in "-.:+" for c in pkg):
            return MessageResponse(message=f"Invalid package name: {pkg}", success=False)

    packages_str = " ".join(req.packages)
    cmd = f"DEBIAN_FRONTEND=noninteractive apt-get remove -y {packages_str}"
    result = await run_command(cmd, timeout=300)
    await log_audit(
        "packages.remove",
        user["id"],
        f"packages={packages_str}",
        success=result.success,
    )
    if not result.success:
        return MessageResponse(message=f"Remove failed: {result.stderr[:500]}", success=False)
    return MessageResponse(message=f"Removed: {packages_str}")


@router.get("/installed", response_model=list[InstalledPackage])
async def list_installed(
    search: str = Query(default="", max_length=100),
    user: dict = Depends(get_current_user),
):
    if search:
        cmd = f"dpkg-query -W -f='${{Package}} ${{Version}}\\n' 2>/dev/null | grep -i '{search}'"
    else:
        cmd = "dpkg-query -W -f='${Package} ${Version}\\n' 2>/dev/null | head -500"

    result = await run_command(cmd)
    packages = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(" ", 1)
        if len(parts) == 2:
            packages.append(InstalledPackage(name=parts[0], version=parts[1]))
    return packages


@router.get("/upgradable", response_model=list[InstalledPackage])
async def list_upgradable(user: dict = Depends(get_current_user)):
    result = await run_command("apt list --upgradable 2>/dev/null | tail -n +2")
    packages = []
    for line in result.stdout.splitlines():
        parts = line.strip().split("/")
        if parts:
            name = parts[0]
            version = parts[1].split(" ")[0] if len(parts) > 1 else "unknown"
            packages.append(InstalledPackage(name=name, version=version))
    return packages
