"""Daytona sandbox service for isolated per-job code generation.

Each APPDEVELOPER job gets its own Daytona sandbox — a full isolated Linux
container with dedicated filesystem, network, and process namespace. The
builder/reviewer/fixer agents execute commands and write files inside the
sandbox instead of the local filesystem.

Environment variables (LLM credentials, API keys) live on the host microservice
and are injected into each sandbox command execution via the ``env`` parameter.
Secrets never touch the sandbox filesystem.

When Daytona is not configured (DAYTONA_API_KEY unset), the service is a no-op
and the existing local WorkspaceService is used as a fallback.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger()

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "https://app.daytona.io/api")
DAYTONA_TARGET = os.getenv("DAYTONA_TARGET", "us")


def is_daytona_configured() -> bool:
    """Return True if Daytona credentials are present."""
    return bool(DAYTONA_API_KEY)


def _get_sandbox_env() -> dict[str, str]:
    """Collect environment variables that must be available inside the sandbox.

    These are read from the host microservice's environment (populated from its
    .env file) and injected per-command into the sandbox. This keeps secrets off
    the sandbox filesystem while making them available to processes that need
    them (e.g., the Claude Agent SDK subprocess, pip install from private repos).

    Only non-empty values are included.
    """
    keys = [
        # LLM routing — needed by the Claude Agent SDK subprocess inside the sandbox
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        # Package/model access (may be needed during validation/install inside sandbox)
        "HUGGING_FACE_HUB_TOKEN",
        # General
        "HOME",
        "PATH",
        "LANG",
    ]
    env: dict[str, str] = {}
    for key in keys:
        val = os.getenv(key, "")
        if val:
            env[key] = val
    # Always ensure a usable PATH inside the sandbox
    if "PATH" not in env:
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


class SandboxService:
    """Manages Daytona sandbox lifecycle for APPDEVELOPER jobs.

    Each job_id maps to one sandbox. Sandboxes are ephemeral (auto-deleted on
    stop) and use the ``daytona-medium`` snapshot (2 vCPU, 4GB RAM, 8GB disk)
    which is suitable for code generation and validation.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._sandboxes: dict[str, Any] = {}  # job_id -> sandbox instance

    def _get_client(self) -> Any:
        if self._client is None:
            from daytona import Daytona, DaytonaConfig

            self._client = Daytona(
                DaytonaConfig(
                    api_key=DAYTONA_API_KEY,
                    api_url=DAYTONA_API_URL,
                    target=DAYTONA_TARGET,
                )
            )
        return self._client

    def create_sandbox(self, job_id: str) -> Any:
        """Create an isolated sandbox for a job. Returns the sandbox instance."""
        from daytona import CreateSandboxFromSnapshotParams

        client = self._get_client()
        sandbox = client.create(
            CreateSandboxFromSnapshotParams(
                snapshot="daytona-medium",
                auto_stop_interval=30,  # stop after 30 min idle
                auto_delete_interval=0,  # delete immediately on stop (ephemeral)
            )
        )
        self._sandboxes[job_id] = sandbox
        logger.info("sandbox_created", job_id=job_id, sandbox_id=sandbox.id)
        return sandbox

    def get_sandbox(self, job_id: str) -> Any | None:
        """Get the sandbox for a job, or None if not created."""
        return self._sandboxes.get(job_id)

    def exec_in_sandbox(
        self,
        job_id: str,
        command: str,
        cwd: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command in the job's sandbox with host env vars injected.

        Environment variables (LLM keys, base URLs) from the host are
        automatically passed to the sandbox process so that tools like the
        Claude Agent SDK can reach the LLM proxy.
        """
        sandbox = self._sandboxes.get(job_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for job {job_id}")

        env = _get_sandbox_env()
        if extra_env:
            env.update(extra_env)

        response = sandbox.process.exec(command, cwd=cwd, env=env, timeout=300)
        return response.exit_code, response.result, ""

    def write_file_in_sandbox(self, job_id: str, path: str, content: str) -> None:
        """Write a file inside the job's sandbox."""
        sandbox = self._sandboxes.get(job_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for job {job_id}")

        # Ensure parent directory exists
        parent = "/".join(path.split("/")[:-1])
        if parent:
            sandbox.fs.create_folder(parent, "755")

        # Upload content as bytes
        sandbox.fs.upload_file(path, content.encode("utf-8"))

    def read_file_in_sandbox(self, job_id: str, path: str) -> str:
        """Read a file from the job's sandbox."""
        sandbox = self._sandboxes.get(job_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for job {job_id}")

        content_bytes = sandbox.fs.download_file(path)
        return content_bytes.decode("utf-8")

    def list_files_in_sandbox(self, job_id: str, path: str = "/workspace") -> list[str]:
        """List files in the job's sandbox workspace."""
        sandbox = self._sandboxes.get(job_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for job {job_id}")

        response = sandbox.process.exec(
            f"find {path} -type f -not -name '.gitignore'",
            env=_get_sandbox_env(),
        )
        if response.exit_code != 0:
            return []
        files = [
            line.replace(f"{path}/", "")
            for line in response.result.strip().split("\n")
            if line.strip()
        ]
        return files

    def destroy_sandbox(self, job_id: str) -> None:
        """Stop and delete the sandbox for a job."""
        sandbox = self._sandboxes.pop(job_id, None)
        if sandbox is not None:
            try:
                sandbox.delete(wait=False)
                logger.info("sandbox_destroyed", job_id=job_id, sandbox_id=sandbox.id)
            except Exception as e:
                logger.warning("sandbox_destroy_failed", job_id=job_id, error=str(e))


# Module-level singleton
sandbox_service = SandboxService()
