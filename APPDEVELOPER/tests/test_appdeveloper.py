from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.models import Database
from app.domain.enums import EventName, JobState, TerminalState
from app.domain.schemas import (
    ArchitectureProposal,
    GitHubPushRequest,
    JobCreate,
    ReviewReport,
)
from app.domain.transitions import is_valid_transition
from app.repositories.job_repository import EventRepository, JobRepository
from app.security.redaction import redact_dict, redact_text, scan_for_secrets
from app.services.agent_service import AgentService
from app.services.architecture_service import ArchitectureService
from app.services.event_service import EventService
from app.services.github_service import GitHubService
from app.services.job_service import JobService
from app.services.review_service import ReviewService
from app.services.validation_service import ValidationService
from app.services.workspace_service import WorkspaceService


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> str:
    return str(tmp_path / "workspaces")


@pytest_asyncio.fixture
async def db() -> Database:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_tables()
    yield database
    await database.dispose()


@pytest_asyncio.fixture
async def job_repo(db: Database) -> JobRepository:
    return JobRepository(db)


@pytest_asyncio.fixture
async def event_repo(db: Database) -> EventRepository:
    return EventRepository(db)


@pytest.fixture
def workspace_service(tmp_workspace: str) -> WorkspaceService:
    return WorkspaceService(tmp_workspace)


@pytest.fixture
def agent_service() -> AgentService:
    return AgentService("test-key")


@pytest_asyncio.fixture
async def event_service(
    event_repo: EventRepository, job_repo: JobRepository
) -> EventService:
    return EventService(event_repo, job_repo)


@pytest.fixture
def validation_service(workspace_service: WorkspaceService) -> ValidationService:
    return ValidationService(workspace_service)


@pytest.fixture
def architecture_service(
    agent_service: AgentService, event_service: EventService
) -> ArchitectureService:
    return ArchitectureService(agent_service, event_service)


@pytest.fixture
def review_service(
    agent_service: AgentService,
    workspace_service: WorkspaceService,
    validation_service: ValidationService,
    event_service: EventService,
) -> ReviewService:
    return ReviewService(
        agent_service, workspace_service, validation_service, event_service
    )


@pytest.fixture
def github_service(
    workspace_service: WorkspaceService, event_service: EventService
) -> GitHubService:
    return GitHubService(workspace_service, event_service)


@pytest_asyncio.fixture
async def job_service(
    job_repo: JobRepository,
    workspace_service: WorkspaceService,
    architecture_service: ArchitectureService,
    agent_service: AgentService,
    validation_service: ValidationService,
    review_service: ReviewService,
    github_service: GitHubService,
    event_service: EventService,
) -> JobService:
    return JobService(
        job_repo=job_repo,
        workspace_service=workspace_service,
        architecture_service=architecture_service,
        agent_service=agent_service,
        validation_service=validation_service,
        review_service=review_service,
        github_service=github_service,
        event_service=event_service,
        max_concurrent=5,
    )


class TestStateTransitions:
    def test_valid_transitions(self) -> None:
        assert is_valid_transition(JobState.CREATED, JobState.ARCHITECTURE_PROPOSED)
        assert is_valid_transition(JobState.CREATED, TerminalState.FAILED)
        assert is_valid_transition(JobState.CREATED, TerminalState.CANCELLED)
        assert is_valid_transition(
            JobState.ARCHITECTURE_PROPOSED, JobState.AWAITING_ANSWERS
        )
        assert is_valid_transition(
            JobState.AWAITING_ANSWERS, JobState.READY_TO_GENERATE
        )
        assert is_valid_transition(JobState.READY_TO_GENERATE, JobState.GENERATING)
        assert is_valid_transition(JobState.GENERATING, JobState.REVIEWING)
        assert is_valid_transition(JobState.REVIEWING, JobState.DEBUGGING)
        assert is_valid_transition(JobState.REVIEWING, JobState.VERIFIED)
        assert is_valid_transition(JobState.VERIFIED, JobState.AWAITING_PUSH_DECISION)
        assert is_valid_transition(
            JobState.AWAITING_PUSH_DECISION, JobState.AWAITING_GITHUB_TOKEN
        )
        assert is_valid_transition(JobState.AWAITING_GITHUB_TOKEN, JobState.PUSHING)
        assert is_valid_transition(JobState.PUSHING, JobState.PUSHED)

    def test_invalid_transitions(self) -> None:
        assert not is_valid_transition(JobState.CREATED, JobState.GENERATING)
        assert not is_valid_transition(JobState.PUSHED, JobState.CREATED)
        assert not is_valid_transition(TerminalState.CANCELLED, JobState.CREATED)
        assert not is_valid_transition(JobState.AWAITING_ANSWERS, JobState.PUSHING)


class TestSecurityRedaction:
    def test_redact_github_token(self) -> None:
        text = "Token: ghp_abcdefghijklmnopqrstuvwxyz123456"
        redacted = redact_text(text)
        assert "ghp_" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_anthropic_key(self) -> None:
        text = "ANTHROPIC_API_KEY=sk-ant-1234567890"
        redacted = redact_text(text)
        assert "sk-ant" not in redacted
        assert "[REDACTED]" in redacted

    def test_scan_for_secrets(self) -> None:
        content = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"  # 36 chars after prefix
        findings = scan_for_secrets(content)
        assert len(findings) > 0

    def test_scan_clean_content(self) -> None:
        content = "This is clean content"
        findings = scan_for_secrets(content)
        assert len(findings) == 0

    def test_redact_dict(self) -> None:
        data = {"key": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij", "safe": "no secrets"}
        redacted = redact_dict(data)
        assert "ghp_" not in redacted["key"]
        assert redacted["safe"] == "no secrets"


class TestWorkspaceService:
    def test_create_workspace(self, workspace_service: WorkspaceService) -> None:
        workspace_id = "test-job-1"
        path = workspace_service.create_workspace(workspace_id)
        assert Path(path).exists()
        assert (Path(path) / ".gitignore").exists()

    def test_create_duplicate_workspace(
        self, workspace_service: WorkspaceService
    ) -> None:
        workspace_id = "test-job-2"
        workspace_service.create_workspace(workspace_id)
        with pytest.raises(ValueError, match="already exists"):
            workspace_service.create_workspace(workspace_id)

    def test_write_and_read_file(self, workspace_service: WorkspaceService) -> None:
        workspace_id = "test-job-3"
        workspace_service.create_workspace(workspace_id)
        workspace_service.write_file(workspace_id, "test.py", "print('hello')")
        content = workspace_service.read_file(workspace_id, "test.py")
        assert content == "print('hello')"

    def test_path_traversal_rejection(
        self, workspace_service: WorkspaceService
    ) -> None:
        workspace_id = "test-job-4"
        workspace_service.create_workspace(workspace_id)
        with pytest.raises(ValueError, match="Path traversal"):
            workspace_service.write_file(workspace_id, "../../etc/passwd", "evil")

    def test_list_files(self, workspace_service: WorkspaceService) -> None:
        workspace_id = "test-job-5"
        workspace_service.create_workspace(workspace_id)
        workspace_service.write_file(workspace_id, "test.py", "print('hello')")
        workspace_service.write_file(workspace_id, "subdir/test2.py", "print('world')")
        files = workspace_service.list_files(workspace_id)
        assert "test.py" in files
        assert "subdir/test2.py" in files


class TestJobService:
    async def test_create_job(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        response = await job_service.create_job(request)
        assert response.state == JobState.CREATED
        assert response.job_id

    async def test_get_job(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        created = await job_service.create_job(request)
        fetched = await job_service.get_job(created.job_id)
        assert fetched.job_id == created.job_id
        assert fetched.state == created.state

    async def test_get_nonexistent_job(self, job_service: JobService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await job_service.get_job("nonexistent")

    async def test_cancel_job(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        created = await job_service.create_job(request)
        cancelled = await job_service.cancel(created.job_id)
        assert cancelled.state == TerminalState.CANCELLED

    async def test_push_decision_not_verified(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        created = await job_service.create_job(request)
        with pytest.raises(ValueError, match="must be verified"):
            await job_service.push_decision(created.job_id, True)

    async def test_submit_answers_wrong_state(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        created = await job_service.create_job(request)
        with pytest.raises(ValueError, match="Not awaiting"):
            await job_service.submit_answers(created.job_id, {"q1": "answer"})


class TestEventService:
    async def test_emit_event(
        self, event_service: EventService, job_repo: JobRepository
    ) -> None:
        await job_repo.create("test-event-1", "test prompt")
        event = await event_service.emit(
            "test-event-1",
            EventName.STATE_CHANGED,
            {"state": "CREATED"},
        )
        assert event.name == EventName.STATE_CHANGED
        assert event.sequence == 1

    async def test_get_snapshot(
        self, event_service: EventService, job_repo: JobRepository
    ) -> None:
        await job_repo.create("test-event-2", "test prompt")
        await event_service.emit(
            "test-event-2", EventName.STATE_CHANGED, {"state": "CREATED"}
        )
        snapshot = await event_service.get_snapshot("test-event-2")
        assert snapshot.job_id == "test-event-2"
        assert len(snapshot.events) == 1

    async def test_subscribe_unsubscribe(self, event_service: EventService) -> None:
        queue = event_service.subscribe("test-job")
        assert "test-job" in event_service._connections
        event_service.unsubscribe("test-job", queue)
        assert "test-job" not in event_service._connections


class TestMockedPlanner:
    @patch.object(AgentService, "run_planner")
    async def test_planner_returns_proposal(
        self, mock_planner: AsyncMock, agent_service: AgentService
    ) -> None:
        mock_planner.return_value = (
            ArchitectureProposal(
                app_type="REST API",
                stack=["Python", "FastAPI"],
                components=["main"],
                data_model={"User": "id: int, name: str"},
                api_boundaries=["GET /users"],
                security_concerns=["Auth required"],
                assumptions=["SQLite for dev"],
                risks=["Single instance"],
                deliverables=["API server"],
            ),
            [],
        )
        proposal, questions = await agent_service.run_planner("Build a user API")
        assert proposal.app_type == "REST API"
        assert len(questions) == 0


class TestMockedReviewer:
    @patch.object(AgentService, "run_reviewer")
    async def test_reviewer_passes(
        self, mock_reviewer: AsyncMock, agent_service: AgentService
    ) -> None:
        mock_reviewer.return_value = ReviewReport(
            findings=[],
            commands_run=["pytest"],
            outcomes={"pytest": True},
            passed=True,
        )
        report = await agent_service.run_reviewer("brief", {}, "output")
        assert report.passed


class TestAPIEndpoints:
    @pytest_asyncio.fixture
    async def client(
        self, job_service: JobService, event_service: EventService
    ) -> AsyncClient:
        from app.main import app

        app.state.job_service = job_service
        app.state.event_service = event_service
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_readiness(self, client: AsyncClient) -> None:
        response = await client.get("/readyz")
        assert response.status_code == 200
        assert response.json()["database"] is True

    async def test_create_job_api(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/jobs",
            json={"prompt": "Build a todo app"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["state"] == "CREATED"

    async def test_get_job_api(self, client: AsyncClient) -> None:
        create_response = await client.post(
            "/v1/jobs",
            json={"prompt": "Build a todo app"},
        )
        job_id = create_response.json()["job_id"]

        response = await client.get(f"/v1/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["job_id"] == job_id

    async def test_get_nonexistent_job_api(self, client: AsyncClient) -> None:
        response = await client.get("/v1/jobs/nonexistent")
        assert response.status_code == 404


class TestSecurityValidation:
    def test_validate_workspace_path_valid(self, tmp_workspace: str) -> None:
        from app.security.validation import validate_workspace_path

        workspace = Path(tmp_workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        job_dir = workspace / "test-job"
        job_dir.mkdir(exist_ok=True)
        (job_dir / "test.py").touch()

        result = validate_workspace_path(tmp_workspace, "test-job", "test.py")
        assert result is not None

    def test_validate_workspace_path_traversal(self, tmp_workspace: str) -> None:
        from app.security.validation import validate_workspace_path

        workspace = Path(tmp_workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        job_dir = workspace / "test-job"
        job_dir.mkdir(exist_ok=True)

        result = validate_workspace_path(tmp_workspace, "test-job", "../../etc/passwd")
        assert result is None

    def test_validate_workspace_path_absolute(self, tmp_workspace: str) -> None:
        from app.security.validation import validate_workspace_path

        workspace = Path(tmp_workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        job_dir = workspace / "test-job"
        job_dir.mkdir(exist_ok=True)

        result = validate_workspace_path(tmp_workspace, "test-job", "/etc/passwd")
        assert result is None


class TestGitHubService:
    async def test_push_requires_confirm(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a todo app")
        created = await job_service.create_job(request)
        push_request = GitHubPushRequest(
            repository_name="test-repo",
            visibility="private",
            token="ghp_test_token",
            confirm=False,
        )
        with pytest.raises(ValueError, match="awaiting GitHub token"):
            await job_service.push_to_github(created.job_id, push_request)


class TestRateLimiter:
    async def test_rate_limit_allows_requests(self) -> None:
        from app.security.rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert await limiter.check("user1") is True
        assert await limiter.check("user1") is True

    async def test_rate_limit_blocks_after_max(self) -> None:
        from app.security.rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert await limiter.check("user1") is True
        assert await limiter.check("user1") is True
        assert await limiter.check("user1") is False


class TestPushFlowRegression:
    """Regression tests for the GitHub push flow state machine.

    Previously push_decision(approved=True) never advanced to
    AWAITING_GITHUB_TOKEN and push_to_github attempted an invalid
    AWAITING_GITHUB_TOKEN -> PUSHED transition, making the push
    flow completely unreachable.
    """

    @pytest.mark.asyncio
    async def test_approved_push_decision_reaches_github_token(
        self, job_service: JobService, job_repo: JobRepository
    ) -> None:
        job = await job_service.create_job(JobCreate(prompt="build a todo app"))
        await job_repo.update_state(job.job_id, JobState.VERIFIED)

        result = await job_service.push_decision(job.job_id, approved=True)
        assert result.state == JobState.AWAITING_GITHUB_TOKEN

    @pytest.mark.asyncio
    async def test_declined_push_decision_cancels(
        self, job_service: JobService, job_repo: JobRepository
    ) -> None:
        job = await job_service.create_job(JobCreate(prompt="build a todo app"))
        await job_repo.update_state(job.job_id, JobState.VERIFIED)

        result = await job_service.push_decision(job.job_id, approved=False)
        assert result.state == TerminalState.CANCELLED

    @pytest.mark.asyncio
    async def test_push_to_github_transitions_through_pushing(
        self, job_service: JobService, job_repo: JobRepository
    ) -> None:
        from app.domain.schemas import GitHubPushResponse

        job = await job_service.create_job(JobCreate(prompt="build a todo app"))
        await job_repo.update_state(job.job_id, JobState.AWAITING_GITHUB_TOKEN)

        job_service._github.push_to_repository = AsyncMock(  # type: ignore[method-assign]
            return_value=GitHubPushResponse(
                html_url="https://github.com/acme/todo",
                commit_sha="abc123",
                repository_created=True,
            )
        )

        request = GitHubPushRequest(
            repository_name="todo", token="ghp_example", confirm=True
        )
        result = await job_service.push_to_github(job.job_id, request)
        assert result.html_url == "https://github.com/acme/todo"

        job_after = await job_service.get_job(job.job_id)
        assert job_after.state == JobState.PUSHED
