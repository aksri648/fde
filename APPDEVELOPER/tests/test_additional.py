import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.db.models import Database
from app.domain.enums import EventName, JobState
from app.domain.schemas import (
    JobCreate,
    ReviewFinding,
    ReviewReport,
)
from app.repositories.job_repository import EventRepository, JobRepository
from app.security.auth import configure_api_key, verify_api_key
from app.services.agent_service import AgentService, MockClaudeClient
from app.services.architecture_service import ArchitectureService
from app.services.event_service import EventService
from app.services.github_service import GitHubService
from app.services.job_service import JobService
from app.services.review_service import ReviewService
from app.services.validation_service import (
    ValidationReport,
    ValidationResult,
    ValidationService,
)
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
def validation_service(
    workspace_service: WorkspaceService,
) -> ValidationService:
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
        max_concurrent=2,
    )


class TestMockClaudeClient:
    async def test_mock_client_query(self) -> None:
        import json

        client = MockClaudeClient()
        # Planner role: returns an architecture proposal with no questions.
        result = await client.query(
            system="You are an expert software architect.",
            message="test",
            max_tokens=100,
        )
        assert "content" in result
        planner_data = json.loads(result["content"])
        assert "app_type" in planner_data
        assert planner_data["questions"] == []

    async def test_mock_client_roles(self) -> None:
        import json

        client = MockClaudeClient()

        builder = json.loads(
            (await client.query(system="You are an expert software developer. Build a complete app.", message="x"))[
                "content"
            ]
        )
        assert "files" in builder and builder["files"]

        reviewer = json.loads(
            (await client.query(system="You are an expert code reviewer.", message="x"))["content"]
        )
        assert reviewer["passed"] is True

        fixer = json.loads(
            (await client.query(system="Your task is to fix issues found by the reviewer.", message="x"))[
                "content"
            ]
        )
        assert "fixes" in fixer


class TestAgentServiceInit:
    def test_agent_service_creation(self) -> None:
        service = AgentService("test-key")
        assert service._api_key == "test-key"

    @patch.object(AgentService, "_get_client")
    async def test_run_planner_exception(self, mock_get_client: AsyncMock) -> None:
        mock_client = AsyncMock()
        mock_client.query.return_value = {"content": "invalid json"}
        mock_get_client.return_value = mock_client

        service = AgentService("test-key")
        with pytest.raises(ValueError, match="Invalid planner output"):
            await service.run_planner("test prompt")


class TestAuth:
    def test_configure_api_key(self) -> None:
        configure_api_key("test-key-123")

    async def test_verify_api_key_no_configured(self) -> None:
        configure_api_key(None)
        result = await verify_api_key()
        assert result == "dev-mode"


class TestValidationReport:
    def test_validation_report_add_pass(self) -> None:
        report = ValidationReport()
        result = ValidationResult(
            command="test",
            passed=True,
            output="ok",
            exit_code=0,
        )
        report.add(result)
        assert report.all_passed
        assert len(report.results) == 1

    def test_validation_report_add_fail(self) -> None:
        report = ValidationReport()
        result = ValidationResult(
            command="test",
            passed=False,
            output="error",
            exit_code=1,
        )
        report.add(result)
        assert not report.all_passed

    def test_validation_report_to_dict(self) -> None:
        report = ValidationReport()
        result = ValidationResult(
            command="test",
            passed=True,
            output="ok",
            exit_code=0,
        )
        report.add(result)
        d = report.to_dict()
        assert "results" in d
        assert "all_passed" in d
        assert d["results"][0]["command"] == "test"


class TestWorkspaceMore:
    def test_write_file_nonexistent_workspace(
        self, workspace_service: WorkspaceService
    ) -> None:
        with pytest.raises(FileNotFoundError):
            workspace_service.write_file("nonexistent", "test.py", "content")

    def test_list_files_nonexistent_workspace(
        self, workspace_service: WorkspaceService
    ) -> None:
        with pytest.raises(FileNotFoundError):
            workspace_service.list_files("nonexistent")


class TestJobServiceMore:
    async def test_job_lifecycle_create(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a REST API")
        job = await job_service.create_job(request)
        assert job.state == JobState.CREATED
        fetched = await job_service.get_job(job.job_id)
        assert fetched.brief is None

    async def test_cancel_already_cancelled(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a REST API")
        job = await job_service.create_job(request)
        await job_service.cancel(job.job_id)
        with pytest.raises(ValueError, match="terminal state"):
            await job_service.cancel(job.job_id)


class TestEventServiceMore:
    async def test_event_redaction(
        self, event_service: EventService, job_repo: JobRepository
    ) -> None:
        await job_repo.create("test-redact", "test prompt")
        event = await event_service.emit(
            "test-redact",
            EventName.AGENT_MESSAGE,
            {"secret": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"},
        )
        assert "ghp_" not in str(event.data)

    async def test_event_truncation(
        self, event_service: EventService, job_repo: JobRepository
    ) -> None:
        await job_repo.create("test-trunc", "test prompt")
        long_data = {"content": "x" * 20000}
        event = await event_service.emit(
            "test-trunc", EventName.AGENT_MESSAGE, long_data
        )
        assert len(event.data["content"]) <= 10020

    async def test_get_snapshot_nonexistent(self, event_service: EventService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await event_service.get_snapshot("nonexistent")


class TestReviewServiceMore:
    async def test_run_review_cycle_max_rounds(
        self,
        review_service: ReviewService,
        workspace_service: WorkspaceService,
        agent_service: AgentService,
    ) -> None:
        job_id = "test-review-rounds"
        workspace_service.create_workspace(job_id)

        with patch.object(
            agent_service,
            "run_reviewer",
            new_callable=AsyncMock,
        ) as mock_reviewer:
            mock_reviewer.return_value = ReviewReport(
                findings=[
                    ReviewFinding(
                        severity="Error",
                        evidence="test evidence",
                        affected_files=["test.py"],
                        required_fix="fix this",
                        passed=False,
                    )
                ],
                passed=False,
                review_rounds=1,
            )

            with patch.object(
                agent_service,
                "run_fixer",
                new_callable=AsyncMock,
            ):
                report = await review_service.run_review_cycle(
                    job_id=job_id,
                    brief="test brief",
                    workspace_path=workspace_service.get_workspace_path(job_id),
                )
                assert not report.passed
                assert report.review_rounds == 3


class TestJobServiceGenerate:
    async def test_generate_wrong_state(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a REST API")
        job = await job_service.create_job(request)
        with pytest.raises(ValueError):
            await job_service.generate(job.job_id)

    async def test_generate_concurrent_limit(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a REST API")
        job1 = await job_service.create_job(request)
        job2 = await job_service.create_job(request)
        job3 = await job_service.create_job(request)

        job_service._active_jobs.add(job1.job_id)
        job_service._active_jobs.add(job2.job_id)

        with pytest.raises(ValueError):
            await job_service.generate(job3.job_id)

    async def test_generate_duplicate_active(self, job_service: JobService) -> None:
        request = JobCreate(prompt="Build a REST API")
        job = await job_service.create_job(request)
        job_service._active_jobs.add(job.job_id)

        with pytest.raises(ValueError):
            await job_service.generate(job.job_id)


class TestWorkspaceServiceMore:
    async def test_subprocess_timeout(
        self, workspace_service: WorkspaceService
    ) -> None:
        job_id = "test-timeout"
        workspace_service.create_workspace(job_id)
        exit_code, stdout, stderr = await workspace_service.run_subprocess(
            ["sleep", "10"],
            workspace_service.get_workspace_path(job_id),
            timeout=1,
        )
        assert exit_code == -1

    def test_subprocess_shell_metacharacters(
        self, workspace_service: WorkspaceService
    ) -> None:
        job_id = "test-shell"
        workspace_service.create_workspace(job_id)
        with pytest.raises(ValueError, match="Shell metacharacters"):
            asyncio.get_event_loop().run_until_complete(
                workspace_service.run_subprocess(
                    ["echo test | grep test"],
                    workspace_service.get_workspace_path(job_id),
                )
            )

    def test_subprocess_empty_command(
        self, workspace_service: WorkspaceService
    ) -> None:
        job_id = "test-empty"
        workspace_service.create_workspace(job_id)
        with pytest.raises(ValueError, match="Empty command"):
            asyncio.get_event_loop().run_until_complete(
                workspace_service.run_subprocess(
                    [],
                    workspace_service.get_workspace_path(job_id),
                )
            )


class TestJobRepositoryMore:
    async def test_update_brief(self, job_repo: JobRepository) -> None:
        await job_repo.create("test-brief", "test prompt")
        await job_repo.update_brief("test-brief", "new brief")
        fetched = await job_repo.get("test-brief")
        assert fetched is not None
        assert fetched.brief == "new brief"

    async def test_update_and_get_answers(self, job_repo: JobRepository) -> None:
        await job_repo.create("test-answers", "test prompt")
        await job_repo.update_answers("test-answers", {"q1": "a1", "q2": "a2"})
        fetched = await job_repo.get("test-answers")
        assert fetched is not None
        assert fetched.get_answers() == {"q1": "a1", "q2": "a2"}

    async def test_update_and_get_questions(self, job_repo: JobRepository) -> None:
        await job_repo.create("test-questions", "test prompt")
        questions = [{"id": "q1", "question": "test?"}]
        await job_repo.update_questions("test-questions", questions)
        fetched = await job_repo.get("test-questions")
        assert fetched is not None
        assert fetched.get_questions() == questions

    async def test_update_and_get_reports(self, job_repo: JobRepository) -> None:
        await job_repo.create("test-reports", "test prompt")
        reports = [{"passed": True, "findings": []}]
        await job_repo.update_reports("test-reports", reports)
        fetched = await job_repo.get("test-reports")
        assert fetched is not None
        assert fetched.get_reports() == reports

    async def test_list_all(self, job_repo: JobRepository) -> None:
        await job_repo.create("test-list-1", "prompt 1")
        await job_repo.create("test-list-2", "prompt 2")
        jobs = await job_repo.list_all()
        assert len(jobs) >= 2


class TestEventRepositoryMore:
    async def test_get_max_sequence_empty(self, event_repo: EventRepository) -> None:
        seq = await event_repo.get_max_sequence("nonexistent")
        assert seq == 0

    async def test_list_for_job_empty(self, event_repo: EventRepository) -> None:
        events = await event_repo.list_for_job("nonexistent")
        assert len(events) == 0

    async def test_multiple_events_ordering(self, event_repo: EventRepository) -> None:
        await event_repo.create(
            "test-order", EventName.STATE_CHANGED, {"state": "1"}, 1
        )
        await event_repo.create(
            "test-order", EventName.STATE_CHANGED, {"state": "2"}, 2
        )
        events = await event_repo.list_for_job("test-order")
        assert len(events) == 2
        assert events[0].sequence < events[1].sequence


class TestGitHubServiceMock:
    async def test_validate_token(self, github_service: GitHubService) -> None:
        with pytest.raises(Exception):
            await github_service.validate_token("test-token")
