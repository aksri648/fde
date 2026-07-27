"""Worker process entry point."""

from __future__ import annotations

import asyncio
import signal

import structlog

from app.services.outbox_worker import OutboxWorker

logger = structlog.get_logger(__name__)


async def main() -> None:
    worker = OutboxWorker()

    loop = asyncio.get_running_loop()
    _shutdown_task: asyncio.Task[None] | None = None

    def handle_signal() -> None:
        nonlocal _shutdown_task
        logger.info("worker_shutdown_signal_received")
        _shutdown_task = asyncio.ensure_future(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
