import asyncio

import structlog

from app.domain.enums import EventName, JobState, TerminalState
from app.domain.schemas import (
    FollowUpQuestion,
    GitHubPushRequest,
    GitHubPushResponse,
    JobCreate,
    JobResponse,
    ReviewReport,
)
from app.domain.transitions import is_valid_transition
from app.repositories.job_repository import JobRepository
from app.services.agent_service import AgentService
from app.services.architecture_service import ArchitectureService
from app.services.event_service import EventService
from app.services.github_service import GitHubService
from app.services.review_service import ReviewService
from app.services.validation_service import ValidationService
from app.services.workspace_service import WorkspaceService

logger = structlog.get_logger()

MAX_CONCURRENT_JOBS = 5


class JobService:
    def __init__(
        self,
        job_repo: JobRepository,
        workspace_service: WorkspaceService,
        architecture_service: ArchitectureService,
        agent_service: AgentService,
        validation_service: ValidationService,
        review_service: ReviewService,
        github_service: GitHubService,
        event_service: EventService,
        max_concurrent: int = MAX_CONCURRENT_JOBS,
    ) -> None:
        self._job_repo = job_repo
        self._workspace = workspace_service
        self._architecture = architecture_service
        self._agent = agent_service
        self._validation = validation_service
        self._review = review_service
        self._github = github_service
        self._events = event_service
        self._max_concurrent = max_concurrent
        self._active_jobs: set[str] = set()
        self._lock = asyncio.Lock()

    def _validate_transition(
        self, current: JobState | TerminalState, target: JobState | TerminalState
    ) -> None:
        if not is_valid_transition(current, target):
            raise ValueError(f"Invalid transition from {current} to {target}")

    async def _update_state(
        self, job_id: str, new_state: JobState | TerminalState
    ) -> None:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        current_state = (
            JobState(job.state)
            if job.state in JobState.__members__.values()
            else TerminalState(job.state)
        )
        self._validate_transition(current_state, new_state)
        await self._job_repo.update_state(job_id, new_state)
        await self._events.emit(job_id, EventName.STATE_CHANGED, {"state": new_state})

    async def create_job(self, request: JobCreate) -> JobResponse:
        import uuid

        job_id = str(uuid.uuid4())
        await self._job_repo.create(job_id, request.prompt)
        self._workspace.create_workspace(job_id)

        await self._events.emit(
            job_id,
            EventName.STATE_CHANGED,
            {"state": JobState.CREATED},
        )

        return JobResponse(
            job_id=job_id,
            state=JobState.CREATED,
        )

    async def run_pipeline(self, job_id: str) -> None:
        """Drive a freshly created job through the full lifecycle.

        Runs the architecture/planning phase and, when no follow-up questions
        are required, proceeds directly to generation and review. This is what
        makes the BACKEND handoff actually produce code: the caller creates a
        job and this method advances it without further manual API calls.

        Errors are logged (and already recorded as job state/events by the
        underlying methods) rather than raised, since this runs as a detached
        background task.
        """
        try:
            response = await self.start_architecture(job_id)
        except Exception:
            logger.exception("pipeline_architecture_failed", job_id=job_id)
            return

        if response.state == JobState.READY_TO_GENERATE:
            await self.generate_safe(job_id)

    async def generate_safe(self, job_id: str) -> None:
        """Run generation, swallowing exceptions for background execution."""
        try:
            await self.generate(job_id)
        except Exception:
            logger.exception("pipeline_generate_failed", job_id=job_id)

    async def get_job(self, job_id: str) -> JobResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        return JobResponse(
            job_id=job.id,
            state=job.state,
            brief=job.brief,
            questions=[FollowUpQuestion(**q) for q in job.get_questions()],
            answers=job.get_answers(),
            reports=[ReviewReport(**r) for r in job.get_reports()],
            artifact_count=job.artifact_count,
        )

    async def start_architecture(self, job_id: str) -> JobResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        await self._update_state(job_id, JobState.ARCHITECTURE_PROPOSED)

        proposal, questions = await self._architecture.propose_architecture(
            job_id=job_id,
            prompt=job.prompt,
        )

        brief = self._architecture.create_brief(proposal, {})
        await self._job_repo.update_brief(job_id, brief)

        if questions:
            await self._job_repo.update_questions(
                job_id,
                [q.model_dump() for q in questions],
            )
            await self._update_state(job_id, JobState.AWAITING_ANSWERS)
        else:
            await self._update_state(job_id, JobState.READY_TO_GENERATE)

        return await self.get_job(job_id)

    async def submit_answers(self, job_id: str, answers: dict[str, str]) -> JobResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        current_state = job.state
        if current_state != JobState.AWAITING_ANSWERS:
            raise ValueError(f"Not awaiting answers, current state: {current_state}")

        existing_answers = job.get_answers()
        existing_answers.update(answers)
        await self._job_repo.update_answers(job_id, existing_answers)

        proposal, new_questions = await self._architecture.propose_architecture(
            job_id=job_id,
            prompt=job.prompt,
            answer_history=existing_answers,
        )

        if new_questions:
            await self._job_repo.update_questions(
                job_id,
                [q.model_dump() for q in new_questions],
            )
            await self._update_state(job_id, JobState.ARCHITECTURE_PROPOSED)
            await self._update_state(job_id, JobState.AWAITING_ANSWERS)
        else:
            brief = self._architecture.create_brief(proposal, existing_answers)
            await self._job_repo.update_brief(job_id, brief)
            await self._update_state(job_id, JobState.READY_TO_GENERATE)

        return await self.get_job(job_id)

    async def generate(self, job_id: str) -> None:
        async with self._lock:
            if len(self._active_jobs) >= self._max_concurrent:
                raise ValueError("Maximum concurrent jobs reached")
            if job_id in self._active_jobs:
                raise ValueError("Job is already being processed")
            self._active_jobs.add(job_id)

        try:
            job = await self._job_repo.get(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")

            if job.state != JobState.READY_TO_GENERATE:
                raise ValueError(f"Not ready to generate, current state: {job.state}")

            await self._update_state(job_id, JobState.GENERATING)

            workspace_path = self._workspace.get_workspace_path(job_id)

            try:
                files = await self._agent.run_builder(
                    brief=job.brief or "",
                    workspace_path=workspace_path,
                )

                for filename, content in files.items():
                    self._workspace.write_file(job_id, filename, content)
                    await self._events.emit(
                        job_id,
                        EventName.FILE_CREATED,
                        {"filename": filename},
                    )

                await self._job_repo.update_artifact_count(job_id, len(files))

            except Exception as e:
                logger.error("generation_failed", job_id=job_id, error=str(e))
                await self._update_state(job_id, TerminalState.FAILED)
                await self._events.emit(
                    job_id,
                    EventName.ERROR,
                    {"error": f"Generation failed: {e}"},
                )
                raise

            await self._update_state(job_id, JobState.REVIEWING)

            try:
                review_report = await self._review.run_review_cycle(
                    job_id=job_id,
                    brief=job.brief or "",
                    workspace_path=workspace_path,
                )

                reports = job.get_reports()
                reports.append(review_report.model_dump())
                await self._job_repo.update_reports(job_id, reports)
                await self._job_repo.update_review_rounds(
                    job_id, review_report.review_rounds
                )

                if review_report.passed:
                    await self._update_state(job_id, JobState.VERIFIED)
                    await self._events.emit(
                        job_id,
                        EventName.COMPLETED,
                        {"message": "Codebase passed verification"},
                    )
                else:
                    await self._update_state(job_id, TerminalState.REVIEW_FAILED)
                    await self._events.emit(
                        job_id,
                        EventName.ERROR,
                        {"error": "Codebase failed review after maximum rounds"},
                    )

            except Exception as e:
                logger.error("review_failed", job_id=job_id, error=str(e))
                await self._update_state(job_id, TerminalState.REVIEW_FAILED)
                await self._events.emit(
                    job_id,
                    EventName.ERROR,
                    {"error": f"Review failed: {e}"},
                )

        finally:
            async with self._lock:
                self._active_jobs.discard(job_id)

    async def push_decision(self, job_id: str, approved: bool) -> JobResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if job.state != JobState.VERIFIED:
            raise ValueError("Job must be verified before push decision")

        if approved:
            await self._update_state(job_id, JobState.AWAITING_PUSH_DECISION)
            await self._update_state(job_id, JobState.AWAITING_GITHUB_TOKEN)
        else:
            await self._update_state(job_id, JobState.AWAITING_PUSH_DECISION)
            await self._update_state(job_id, TerminalState.CANCELLED)
            await self._events.emit(
                job_id,
                EventName.COMPLETED,
                {"message": "Push declined by user"},
            )

        return await self.get_job(job_id)

    async def push_to_github(
        self,
        job_id: str,
        request: GitHubPushRequest,
    ) -> GitHubPushResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if job.state != JobState.AWAITING_GITHUB_TOKEN:
            raise ValueError(
                f"Job must be awaiting GitHub token, current state: {job.state}"
            )

        if not request.confirm:
            raise ValueError("confirm must be true to proceed with push")

        token = request.token.get_secret_value()
        await self._update_state(job_id, JobState.PUSHING)
        try:
            result = await self._github.push_to_repository(
                job_id=job_id,
                token=token,
                repository_name=request.repository_name,
                visibility=request.visibility,
                owner=request.owner,
            )

            await self._update_state(job_id, JobState.PUSHED)
            await self._events.emit(
                job_id,
                EventName.COMPLETED,
                {"message": "Successfully pushed to GitHub", "url": result.html_url},
            )

            return result

        except Exception as e:
            logger.error("push_failed", job_id=job_id, error=str(e))
            await self._update_state(job_id, TerminalState.PUSH_FAILED)
            await self._events.emit(
                job_id,
                EventName.ERROR,
                {"error": f"Push failed: {e}"},
            )
            raise

    async def cancel(self, job_id: str) -> JobResponse:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        current_state = (
            JobState(job.state)
            if job.state in JobState.__members__.values()
            else TerminalState(job.state)
        )

        terminal_states = {
            TerminalState.CANCELLED,
            TerminalState.FAILED,
            TerminalState.REVIEW_FAILED,
            TerminalState.PUSH_FAILED,
            JobState.PUSHED,
        }
        if current_state in terminal_states:
            raise ValueError(f"Job is already in terminal state: {current_state}")

        await self._update_state(job_id, TerminalState.CANCELLED)
        await self._events.emit(
            job_id,
            EventName.COMPLETED,
            {"message": "Job cancelled"},
        )

        return await self.get_job(job_id)
