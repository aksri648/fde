import os
import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger()

GITIGNORE_CONTENT = """
.env
.env.*
!.env.example
*.pyc
__pycache__
venv/
.venv/
*.egg-info/
dist/
build/
*.db
*.sqlite3
.githistory
.git
"""

SUBPROCESS_TIMEOUT = 300
MAX_OUTPUT_SIZE = 100000

VALIDATION_COMMANDS = {
    "ruff check .",
    "ruff format --check .",
    "mypy app",
    "bandit -q -r app",
    "pytest -q --cov=app --cov-fail-under=80",
}


class WorkspaceService:
    def __init__(self, workspace_root: str) -> None:
        self._root = Path(workspace_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, job_id: str) -> str:
        job_dir = self._root / job_id
        if job_dir.exists():
            raise ValueError(f"Workspace already exists for job {job_id}")
        job_dir.mkdir(parents=True, exist_ok=True)
        gitignore_path = job_dir / ".gitignore"
        gitignore_path.write_text(GITIGNORE_CONTENT)
        logger.info("workspace_created", job_id=job_id, path=str(job_dir))
        return str(job_dir)

    def get_workspace_path(self, job_id: str) -> str:
        job_dir = self._root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(f"Workspace not found for job {job_id}")
        return str(job_dir)

    def delete_workspace(self, job_id: str) -> None:
        job_dir = self._root / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
            logger.info("workspace_deleted", job_id=job_id)

    def write_file(self, job_id: str, relative_path: str, content: str) -> str:
        job_dir = self._root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(f"Workspace not found for job {job_id}")

        target = (job_dir / relative_path).resolve()
        if not str(target).startswith(str(job_dir.resolve())):
            raise ValueError("Path traversal detected")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        logger.info("file_written", job_id=job_id, path=relative_path)
        return str(target)

    def read_file(self, job_id: str, relative_path: str) -> str:
        job_dir = self._root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(f"Workspace not found for job {job_id}")

        target = (job_dir / relative_path).resolve()
        if not str(target).startswith(str(job_dir.resolve())):
            raise ValueError("Path traversal detected")

        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        return target.read_text()

    def list_files(self, job_id: str) -> list[str]:
        job_dir = self._root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(f"Workspace not found for job {job_id}")

        files: list[str] = []
        for item in job_dir.rglob("*"):
            if item.is_file() and item.name != ".gitignore":
                rel = item.relative_to(job_dir)
                files.append(str(rel))
        return files

    async def run_subprocess(
        self,
        command: list[str],
        cwd: str,
        timeout: int = SUBPROCESS_TIMEOUT,
    ) -> tuple[int, str, str]:
        import asyncio

        if not command:
            raise ValueError("Empty command")

        if any(
            any(char in arg for char in ["|", "&", ";", "$", "`"]) for arg in command
        ):
            raise ValueError("Shell metacharacters not allowed")

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "en_US.UTF-8",
        }

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return -1, "", "Process timed out"

        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]

        return process.returncode or 0, stdout_str, stderr_str
