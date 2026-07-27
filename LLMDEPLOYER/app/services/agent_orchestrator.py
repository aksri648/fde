import json

from app.services.session_manager import session_manager
from app.services.connection_manager import connection_manager
from app.agent.agent_runner import run_deployment_agent
from app.utils.logger import get_logger

logger = get_logger("agent_orchestrator")


async def orchestrate_deployment(session_id: str):
    try:
        session = session_manager.get_session(session_id)
        requirements = session.requirements

        if not requirements:
            session_manager.update_status(session_id, "failed")
            await connection_manager.send_to_session(
                session_id,
                {"type": "error", "payload": {"message": "No requirements found for session"}},
            )
            return

        # Create an isolated Daytona sandbox for this deployment session (if configured)
        from app.services.sandbox_service import is_daytona_configured, sandbox_service

        sandbox = None
        if is_daytona_configured():
            try:
                sandbox = sandbox_service.create_sandbox(session_id)
                await connection_manager.send_to_session(
                    session_id,
                    {"type": "status_update", "payload": {"status": "sandbox_ready", "detail": f"Sandbox {sandbox.id} ready"}},
                )
            except Exception as e:
                logger.error(f"Sandbox creation failed, continuing without isolation: {e}")

        session_manager.update_status(session_id, "deploying")
        await connection_manager.send_to_session(
            session_id,
            {"type": "status_update", "payload": {"status": "deploying", "detail": "Starting deployment analysis..."}},
        )

        async def on_message(text: str):
            await connection_manager.send_to_session(
                session_id,
                {"type": "agent_message", "payload": {"text": text}},
            )

        async def on_status(status: str):
            await connection_manager.send_to_session(
                session_id,
                {"type": "status_update", "payload": {"status": status}},
            )
            session_manager.update_status(session_id, status)

        requirements_dict = requirements.model_dump()
        await run_deployment_agent(session_id, requirements_dict, on_message, on_status)

        session_manager.update_status(session_id, "completed")
        await connection_manager.send_to_session(
            session_id,
            {"type": "deployment_complete", "payload": {"status": "completed", "message": "Deployment completed successfully"}},
        )

    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        session_manager.update_status(session_id, "failed")
        await connection_manager.send_to_session(
            session_id,
            {"type": "error", "payload": {"message": f"Deployment failed: {str(e)}"}},
        )
    finally:
        # Clean up the sandbox regardless of success/failure
        from app.services.sandbox_service import is_daytona_configured, sandbox_service

        if is_daytona_configured():
            sandbox_service.destroy_sandbox(session_id)
