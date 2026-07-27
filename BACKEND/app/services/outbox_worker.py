"""Outbox worker for processing handoff deliveries."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import structlog

from app.config import settings
from app.db.models import HandoffOutbox, HandoffReceiptModel
from app.db.session import async_session_factory
from app.domain.enums import SessionState
from app.repositories.audit_repository import AuditRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.session_repository import SessionRepository
from app.services.event_service import event_broadcaster

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"


class OutboxWorker:
    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("outbox_worker_started", worker_id=WORKER_ID)

        while self._running:
            try:
                await self._process_pending_entries()
            except Exception as e:
                logger.error("outbox_worker_error", error=str(e))

            await asyncio.sleep(settings.outbox_poll_seconds)

    async def stop(self) -> None:
        self._running = False
        logger.info("outbox_worker_stopped", worker_id=WORKER_ID)

    async def _process_pending_entries(self) -> None:
        async with async_session_factory() as db:
            outbox_repo = OutboxRepository(db)
            pending = await outbox_repo.get_pending_entries(limit=5)

            for entry in pending:
                try:
                    await outbox_repo.lock_entry(entry, WORKER_ID)
                    downstream_result = await self._deliver_entry(db, entry)
                    await outbox_repo.mark_completed(entry)

                    await self._create_receipt_and_update_session(db, entry, downstream_result)

                    await db.commit()

                except Exception as e:
                    logger.error(
                        "outbox_delivery_failed",
                        entry_id=str(entry.id),
                        error=str(e),
                    )
                    await outbox_repo.mark_failed(entry, str(e))
                    if entry.status == "FAILED":
                        await self._mark_session_handoff_failed(db, entry, str(e))
                    await db.commit()

    async def _deliver_entry(self, db: AsyncSession, entry: HandoffOutbox) -> dict[str, str]:
        route = entry.route
        # Ensure the downstream receives the persisted idempotency key so that
        # retries are deduplicated at the downstream service.
        package = {**entry.package_json, "idempotency_key": str(entry.idempotency_key)}

        if route == "APPDEVELOPER":
            from app.clients.appdeveloper_client import AppDeveloperClient

            app_client = AppDeveloperClient()
            return await app_client.create_job(package)

        elif route == "LLMDEPLOYER":
            from app.clients.llmdeployer_client import LLMDeployerClient

            deploy_client = LLMDeployerClient()
            return await deploy_client.create_deployment_session(package)

        else:
            raise ValueError(f"Unknown route: {route}")

    async def _mark_session_handoff_failed(
        self, db: AsyncSession, entry: HandoffOutbox, error: str
    ) -> None:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_id(entry.session_id)
        if session and session.state == SessionState.HANDOFF_QUEUED.value:
            await session_repo.update_state(session, SessionState.HANDOFF_FAILED.value)

            audit = AuditRepository(db)
            await audit.create_event(
                actor=WORKER_ID,
                action="handoff_failed",
                session_id=entry.session_id,
                proposal_version=entry.plan_version,
                sanitized_metadata={"route": entry.route, "error": error[:500]},
            )

            await event_broadcaster.publish(
                str(entry.session_id),
                "handoff_failed",
                {
                    "session_id": str(entry.session_id),
                    "route": entry.route,
                    "plan_version": entry.plan_version,
                },
            )

    async def _create_receipt_and_update_session(
        self, db: AsyncSession, entry: HandoffOutbox, downstream_result: dict[str, str]
    ) -> None:
        downstream_id = downstream_result.get("job_id") or downstream_result.get("session_id", "")
        downstream_status = downstream_result.get("state") or downstream_result.get("status", "accepted")

        receipt = HandoffReceiptModel(
            session_id=entry.session_id,
            outbox_id=entry.id,
            route=entry.route,
            idempotency_key=entry.idempotency_key,
            downstream_id=downstream_id,
            downstream_status=downstream_status,
            attempt_count=entry.attempt_count + 1,
        )
        db.add(receipt)

        session_repo = SessionRepository(db)
        session = await session_repo.get_by_id(entry.session_id)
        if session:
            await session_repo.update_state(session, SessionState.HANDED_OFF.value)

        audit = AuditRepository(db)
        await audit.create_event(
            actor=WORKER_ID,
            action="handoff_completed",
            session_id=entry.session_id,
            proposal_version=entry.plan_version,
            sanitized_metadata={
                "route": entry.route,
                "idempotency_key": str(entry.idempotency_key),
            },
        )

        await event_broadcaster.publish(
            str(entry.session_id),
            "handoff_completed",
            {
                "session_id": str(entry.session_id),
                "route": entry.route,
                "plan_version": entry.plan_version,
            },
        )
