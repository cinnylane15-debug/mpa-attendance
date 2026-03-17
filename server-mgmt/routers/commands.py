from fastapi import APIRouter, Depends

from auth import get_current_user
from database import log_audit
from models import CommandRequest, CommandResponse
from utils.shell import run_command

router = APIRouter(prefix="/commands", tags=["Command Execution"])


@router.post("/execute", response_model=CommandResponse)
async def execute_command(
    req: CommandRequest, user: dict = Depends(get_current_user)
):
    result = await run_command(
        command=req.command,
        timeout=req.timeout,
        cwd=req.cwd,
    )

    await log_audit(
        "commands.execute",
        user["id"],
        f"cmd={req.command[:200]}, cwd={req.cwd}, rc={result.returncode}",
        success=result.success,
    )

    return CommandResponse(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        success=result.success,
    )
