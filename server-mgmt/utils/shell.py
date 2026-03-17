import asyncio
import shlex
from dataclasses import dataclass


@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return self.stdout if self.success else self.stderr


async def run_command(
    command: str,
    timeout: int = 120,
    cwd: str | None = None,
    env: dict | None = None,
) -> ShellResult:
    """Run a shell command asynchronously and return the result."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return ShellResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace").strip(),
            stderr=stderr.decode("utf-8", errors="replace").strip(),
        )
    except asyncio.TimeoutError:
        process.kill()
        return ShellResult(returncode=-1, stdout="", stderr=f"Command timed out after {timeout}s")
    except Exception as e:
        return ShellResult(returncode=-1, stdout="", stderr=str(e))


async def run_command_list(
    args: list[str],
    timeout: int = 120,
    cwd: str | None = None,
) -> ShellResult:
    """Run a command with explicit args (no shell injection risk)."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return ShellResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace").strip(),
            stderr=stderr.decode("utf-8", errors="replace").strip(),
        )
    except asyncio.TimeoutError:
        process.kill()
        return ShellResult(returncode=-1, stdout="", stderr=f"Command timed out after {timeout}s")
    except Exception as e:
        return ShellResult(returncode=-1, stdout="", stderr=str(e))
