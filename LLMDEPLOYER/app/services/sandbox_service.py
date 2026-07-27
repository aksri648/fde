"""Daytona sandbox service for isolated per-session deployment execution.

Each LLMDEPLOYER deployment session gets its own Daytona sandbox. The agent's
deployment tools (docker commands, cloud CLI calls, Kubernetes manifests) run
inside the sandbox rather than on the host.

Environment variables (cloud credentials, API keys) live on the host
microservice and are injected into each sandbox command execution via the
``env`` parameter. Secrets never touch the sandbox filesystem.

When Daytona is not configured (DAYTONA_API_KEY unset), the service is a no-op
and tools execute locally (existing behavior).
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("sandbox_service")


def is_daytona_configured() -> bool:
    """Return True if Daytona credentials are present."""
    settings = get_settings()
    return bool(settings.DAYTONA_API_KEY)


def _get_sandbox_env() -> dict[str, str]:
    """Collect environment variables that must be available inside the sandbox.

    These are read from the host microservice's settings (populated from its
    .env file) and injected per-command into the sandbox. This keeps secrets off
    the sandbox filesystem while making them available to deployment tools.

    Only non-empty values are included.
    """
    import os

    settings = get_settings()

    # Start with cloud credentials from the config
    env_map: dict[str, str] = {
        # Azure
        "AZURE_TENANT_ID": settings.AZURE_TENANT_ID,
        "AZURE_CLIENT_ID": settings.AZURE_CLIENT_ID,
        "AZURE_CLIENT_SECRET": settings.AZURE_CLIENT_SECRET,
        "AZURE_SUBSCRIPTION_ID": settings.AZURE_SUBSCRIPTION_ID,
        # RunPod
        "RUNPOD_API_KEY": settings.RUNPOD_API_KEY,
        # Modal
        "MODAL_TOKEN_ID": settings.MODAL_TOKEN_ID,
        "MODAL_TOKEN_SECRET": settings.MODAL_TOKEN_SECRET,
        # NVIDIA NGC / NIM
        "NGC_API_KEY": settings.NGC_API_KEY,
        # HuggingFace (for gated model access)
        "HUGGING_FACE_HUB_TOKEN": settings.HUGGING_FACE_HUB_TOKEN,
        # LLM proxy (in case any tool inside the sandbox needs to call the LLM)
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "ANTHROPIC_BASE_URL": settings.ANTHROPIC_BASE_URL,
    }

    # Filter out empty values
    env = {k: v for k, v in env_map.items() if v}

    # Ensure a usable PATH and HOME inside the sandbox
    env.setdefault("PATH", os.getenv("PATH", "/usr/local/bin:/usr/bin:/bin"))
    env.setdefault("HOME", "/root")

    return env


class SandboxService:
    """Manages Daytona sandbox lifecycle for LLMDEPLOYER sessions.

    Each session_id maps to one sandbox. Sandboxes are ephemeral and use the
    ``daytona-medium`` snapshot for executing deployment CLI tools.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._sandboxes: dict[str, Any] = {}  # session_id -> sandbox

    def _get_client(self) -> Any:
        if self._client is None:
            from daytona import Daytona, DaytonaConfig

            settings = get_settings()
            self._client = Daytona(
                DaytonaConfig(
                    api_key=settings.DAYTONA_API_KEY,
                    api_url=settings.DAYTONA_API_URL,
                    target=settings.DAYTONA_TARGET,
                )
            )
        return self._client

    def create_sandbox(self, session_id: str) -> Any:
        """Create an isolated sandbox for a deployment session."""
        from daytona import CreateSandboxFromSnapshotParams

        client = self._get_client()
        sandbox = client.create(
            CreateSandboxFromSnapshotParams(
                snapshot="daytona-medium",
                auto_stop_interval=30,
                auto_delete_interval=0,  # ephemeral
            )
        )
        self._sandboxes[session_id] = sandbox
        logger.info(f"sandbox_created session_id={session_id} sandbox_id={sandbox.id}")
        return sandbox

    def get_sandbox(self, session_id: str) -> Any | None:
        """Get the sandbox for a session, or None."""
        return self._sandboxes.get(session_id)

    def exec_command(
        self,
        session_id: str,
        command: str,
        cwd: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command in the session's sandbox with host env vars injected.

        Cloud credentials (Azure, RunPod, Modal, NGC) and LLM keys from the
        host are automatically passed so deployment tools can authenticate.
        """
        sandbox = self._sandboxes.get(session_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for session {session_id}")

        env = _get_sandbox_env()
        if extra_env:
            env.update(extra_env)

        response = sandbox.process.exec(command, cwd=cwd, env=env, timeout=600)
        return response.exit_code, response.result, ""

    def write_file(self, session_id: str, path: str, content: str) -> None:
        """Write a file inside the session's sandbox."""
        sandbox = self._sandboxes.get(session_id)
        if sandbox is None:
            raise ValueError(f"No sandbox for session {session_id}")

        parent = "/".join(path.split("/")[:-1])
        if parent:
            sandbox.fs.create_folder(parent, "755")
        sandbox.fs.upload_file(path, content.encode("utf-8"))

    def destroy_sandbox(self, session_id: str) -> None:
        """Stop and delete the sandbox for a session."""
        sandbox = self._sandboxes.pop(session_id, None)
        if sandbox is not None:
            try:
                sandbox.delete(wait=False)
                logger.info(f"sandbox_destroyed session_id={session_id}")
            except Exception as e:
                logger.warning(f"sandbox_destroy_failed session_id={session_id} error={e}")


# Module-level singleton
sandbox_service = SandboxService()
