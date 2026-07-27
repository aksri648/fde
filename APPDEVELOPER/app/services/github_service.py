from typing import Any

import httpx
import structlog

from app.domain.enums import EventName
from app.domain.schemas import GitHubPushResponse
from app.security.redaction import scan_for_secrets
from app.services.event_service import EventService
from app.services.workspace_service import WorkspaceService

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_TIMEOUT = 30


class GitHubService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        event_service: EventService,
    ) -> None:
        self._workspace = workspace_service
        self._events = event_service

    async def validate_token(self, token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
            )
            response.raise_for_status()
            return response.json()

    async def create_repository(
        self,
        token: str,
        name: str,
        visibility: str,
        owner: str | None = None,
    ) -> dict[str, Any]:
        user_info = await self.validate_token(token)
        authenticated_user = user_info.get("login", "")

        if owner and owner != authenticated_user:
            raise ValueError(
                f"Owner '{owner}' does not match authenticated user "
                f"'{authenticated_user}'"
            )

        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
            payload: dict[str, Any] = {
                "name": name,
                "private": visibility == "private",
                "auto_init": False,
            }

            response = await client.post(
                f"{GITHUB_API_BASE}/user/repos",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
            )

            if response.status_code == 422:
                raise ValueError(f"Repository '{name}' already exists")

            response.raise_for_status()
            return response.json()

    async def push_to_repository(
        self,
        job_id: str,
        token: str,
        repository_name: str,
        visibility: str,
        owner: str | None = None,
    ) -> GitHubPushResponse:
        workspace_path = self._workspace.get_workspace_path(job_id)

        await self._events.emit(
            job_id,
            EventName.GITHUB_STATUS,
            {"status": "creating_repository"},
        )

        repo_info = await self.create_repository(
            token, repository_name, visibility, owner
        )
        clone_url = repo_info.get("clone_url", "")
        html_url = repo_info.get("html_url", "")

        await self._events.emit(
            job_id,
            EventName.GITHUB_STATUS,
            {"status": "repository_created", "url": html_url},
        )

        exit_code, stdout, stderr = await self._workspace.run_subprocess(
            ["git", "init"],
            workspace_path,
        )
        if exit_code != 0:
            raise RuntimeError(f"git init failed: {stderr}")

        exit_code, stdout, stderr = await self._workspace.run_subprocess(
            ["git", "add", "."],
            workspace_path,
        )
        if exit_code != 0:
            raise RuntimeError(f"git add failed: {stderr}")

        staged_content = await self._get_staged_content(workspace_path)
        secrets_found = scan_for_secrets(staged_content)
        if secrets_found:
            raise ValueError(f"Secrets detected in staged content: {secrets_found}")

        exit_code, stdout, stderr = await self._workspace.run_subprocess(
            ["git", "commit", "-m", "Initial commit from APPDEVELOPER"],
            workspace_path,
        )
        if exit_code != 0:
            raise RuntimeError(f"git commit failed: {stderr}")

        commit_sha = await self._get_head_commit(workspace_path)

        exit_code, stdout, stderr = await self._workspace.run_subprocess(
            ["git", "branch", "-M", "main"],
            workspace_path,
        )
        if exit_code != 0:
            raise RuntimeError(f"git branch failed: {stderr}")

        auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
        exit_code, stdout, stderr = await self._workspace.run_subprocess(
            ["git", "remote", "add", "origin", auth_url],
            workspace_path,
        )
        if exit_code != 0:
            raise RuntimeError(f"git remote add failed: {stderr}")

        await self._events.emit(
            job_id,
            EventName.GITHUB_STATUS,
            {"status": "pushing"},
        )

        try:
            exit_code, stdout, stderr = await self._workspace.run_subprocess(
                ["git", "push", "-u", "origin", "main"],
                workspace_path,
            )
            if exit_code != 0:
                raise RuntimeError(f"git push failed: {stderr}")
        finally:
            await self._workspace.run_subprocess(
                ["git", "remote", "remove", "origin"],
                workspace_path,
            )

        await self._events.emit(
            job_id,
            EventName.GITHUB_STATUS,
            {"status": "pushed", "url": html_url},
        )

        return GitHubPushResponse(
            html_url=html_url,
            commit_sha=commit_sha,
            repository_created=True,
        )

    async def _get_staged_content(self, workspace_path: str) -> str:
        exit_code, stdout, _ = await self._workspace.run_subprocess(
            ["git", "diff", "--cached", "--name-only"],
            workspace_path,
        )
        if exit_code != 0:
            return ""

        files = stdout.strip().split("\n")
        content_parts: list[str] = []
        for file in files:
            if file:
                try:
                    exit_code, stdout, _ = await self._workspace.run_subprocess(
                        ["git", "show", f":{file}"],
                        workspace_path,
                    )
                    if exit_code == 0:
                        content_parts.append(stdout)
                except Exception:
                    pass
        return "\n".join(content_parts)

    async def _get_head_commit(self, workspace_path: str) -> str:
        exit_code, stdout, _ = await self._workspace.run_subprocess(
            ["git", "rev-parse", "HEAD"],
            workspace_path,
        )
        return stdout.strip() if exit_code == 0 else ""
