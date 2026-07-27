import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from app.domain.enums import EventName
from app.domain.schemas import ReviewReport
from app.services.agent_service import AgentService
from app.services.event_service import EventService
from app.services.validation_service import ValidationService
from app.services.workspace_service import WorkspaceService

logger = structlog.get_logger()

MAX_REVIEW_ROUNDS = 3


class ReviewService:
    def __init__(
        self,
        agent_service: AgentService,
        workspace_service: WorkspaceService,
        validation_service: ValidationService,
        event_service: EventService,
    ) -> None:
        self._agent = agent_service
        self._workspace = workspace_service
        self._validation = validation_service
        self._events = event_service

    async def run_review_cycle(
        self,
        job_id: str,
        brief: str,
        workspace_path: str,
        on_event: (
            Callable[[str, EventName, dict[str, Any]], Coroutine[Any, Any, None]] | None
        ) = None,
    ) -> ReviewReport:
        max_rounds = MAX_REVIEW_ROUNDS
        last_report = ReviewReport(review_rounds=0, passed=False)

        for round_num in range(1, max_rounds + 1):
            logger.info("review_round_start", job_id=job_id, round=round_num)

            await self._events.emit(
                job_id,
                EventName.VALIDATION_STARTED,
                {"round": round_num},
            )

            validation_report = await self._validation.validate_generated_app(job_id)
            validation_output = str(validation_report.to_dict())

            files = {}
            for f in self._workspace.list_files(job_id):
                with contextlib.suppress(Exception):
                    files[f] = self._workspace.read_file(job_id, f)

            try:
                review_report = await self._agent.run_reviewer(
                    brief=brief,
                    files=files,
                    validation_output=validation_output,
                )
                review_report.review_rounds = round_num
            except Exception as e:
                logger.error("reviewer_error", job_id=job_id, error=str(e))
                review_report = ReviewReport(
                    findings=[],
                    review_rounds=round_num,
                    passed=False,
                    risks=[f"Reviewer failed: {e}"],
                )

            await self._events.emit(
                job_id,
                EventName.VALIDATION_RESULT,
                {"round": round_num, "passed": review_report.passed},
            )

            for finding in review_report.findings:
                await self._events.emit(
                    job_id,
                    EventName.REVIEW_FINDING,
                    {
                        "severity": finding.severity,
                        "evidence": finding.evidence,
                        "affected_files": finding.affected_files,
                    },
                )

            if review_report.passed:
                logger.info("review_passed", job_id=job_id, rounds=round_num)
                return review_report

            failed_findings = [f for f in review_report.findings if not f.passed]
            if not failed_findings:
                logger.info("review_no_fixes_needed", job_id=job_id)
                return review_report

            if round_num < max_rounds:
                logger.info("running_fixer", job_id=job_id, round=round_num)
                try:
                    await self._agent.run_fixer(
                        findings=failed_findings,
                        workspace_path=workspace_path,
                    )
                except Exception as e:
                    logger.error("fixer_error", job_id=job_id, error=str(e))

            last_report = review_report

        logger.warning(
            "review_max_rounds_exceeded",
            job_id=job_id,
            rounds=max_rounds,
        )
        return last_report
