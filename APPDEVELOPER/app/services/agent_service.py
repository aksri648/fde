import asyncio
import json
from typing import Any

import structlog

from app.domain.schemas import (
    ArchitectureProposal,
    FollowUpQuestion,
    ReviewFinding,
    ReviewReport,
)
from app.prompts.versions import (
    BUILDER_PROMPT,
    FIXER_PROMPT,
    PLANNER_PROMPT,
    REVIEWER_PROMPT,
)

logger = structlog.get_logger()


class AgentService:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = "") -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            # Use the real Claude Agent SDK when the proxy is configured. The
            # minimum signal for "real mode" is ANTHROPIC_BASE_URL being set —
            # that means the user has a LiteLLM proxy running. ANTHROPIC_API_KEY
            # alone is not sufficient because the SDK spawns a CLI subprocess
            # that may hang without a reachable endpoint.
            has_real_config = bool(self._base_url)

            if has_real_config:
                try:
                    self._client = ClaudeAgentSDKClient(
                        base_url=self._base_url,
                        api_key=self._api_key,
                        model=self._model,
                    )
                    return self._client
                except Exception as e:  # noqa: BLE001 - fall back to mock on any issue
                    logger.warning(
                        "claude_agent_sdk_init_failed_using_mock", error=str(e)
                    )
                    self._client = MockClaudeClient()
                    return self._client

            # No LLM proxy endpoint configured: use a deterministic offline
            # mock so the job pipeline still runs without external services.
            logger.warning("llm_endpoint_not_configured_using_mock_client")
            self._client = MockClaudeClient()
        return self._client

    async def run_planner(
        self,
        prompt: str,
        answer_history: dict[str, str] | None = None,
        on_event: Any = None,
    ) -> tuple[ArchitectureProposal, list[FollowUpQuestion]]:
        client = await self._get_client()

        system_prompt = PLANNER_PROMPT
        user_message = f"App idea: {prompt}"
        if answer_history:
            user_message += f"\n\nPrevious answers: {json.dumps(answer_history)}"

        try:
            response = await client.query(
                system=system_prompt,
                message=user_message,
                max_tokens=4096,
            )

            content = response.get("content", "")
            data = json.loads(content)

            proposal = ArchitectureProposal(
                app_type=data.get("app_type", "Unknown"),
                stack=data.get("stack", []),
                components=data.get("components", []),
                data_model=data.get("data_model", {}),
                api_boundaries=data.get("api_boundaries", []),
                security_concerns=data.get("security_concerns", []),
                assumptions=data.get("assumptions", []),
                risks=data.get("risks", []),
                deliverables=data.get("deliverables", []),
            )

            questions = []
            for q in data.get("questions", []):
                questions.append(
                    FollowUpQuestion(
                        id=q.get("id", ""),
                        question=q.get("question", ""),
                        options=q.get("options", []),
                        required=q.get("required", True),
                    )
                )

            return proposal, questions

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("planner_parse_error", error=str(e))
            raise ValueError(f"Invalid planner output: {e}") from e

    async def run_builder(
        self,
        brief: str,
        workspace_path: str,
        on_event: Any = None,
    ) -> dict[str, str]:
        client = await self._get_client()

        system_prompt = BUILDER_PROMPT
        user_message = (
            f"Build the application based on this brief:\n{brief}\n\n"
            f"Workspace: {workspace_path}"
        )

        try:
            response = await client.query(
                system=system_prompt,
                message=user_message,
                max_tokens=16384,
                tools=["write_file", "create_directory"],
            )

            content = response.get("content", "")

            files: dict[str, str] = {}
            try:
                data = json.loads(content)
                if "files" in data:
                    files = data["files"]
            except json.JSONDecodeError:
                files["generated_code.py"] = content

            return files

        except Exception as e:
            logger.error("builder_error", error=str(e))
            raise

    async def run_reviewer(
        self,
        brief: str,
        files: dict[str, str],
        validation_output: str,
        on_event: Any = None,
    ) -> ReviewReport:
        client = await self._get_client()

        system_prompt = REVIEWER_PROMPT
        user_message = f"""Review this generated application:

Brief:
{brief}

Generated files:
{json.dumps({k: v[:1000] for k, v in files.items()}, indent=2)}

Validation output:
{validation_output}
"""

        try:
            response = await client.query(
                system=system_prompt,
                message=user_message,
                max_tokens=4096,
            )

            content = response.get("content", "")
            data = json.loads(content)

            findings = []
            for f in data.get("findings", []):
                findings.append(
                    ReviewFinding(
                        severity=f.get("severity", "Info"),
                        evidence=f.get("evidence", ""),
                        affected_files=f.get("affected_files", []),
                        required_fix=f.get("required_fix", ""),
                        passed=f.get("passed", False),
                    )
                )

            return ReviewReport(
                findings=findings,
                commands_run=data.get("commands_run", []),
                outcomes=data.get("outcomes", {}),
                failed_tests=data.get("failed_tests", []),
                risks=data.get("risks", []),
                review_rounds=data.get("review_rounds", 1),
                passed=data.get("passed", False),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("reviewer_parse_error", error=str(e))
            raise ValueError(f"Invalid reviewer output: {e}") from e

    async def run_fixer(
        self,
        findings: list[ReviewFinding],
        workspace_path: str,
        on_event: Any = None,
    ) -> dict[str, str]:
        client = await self._get_client()

        system_prompt = FIXER_PROMPT
        user_message = f"""Fix these issues:

{json.dumps([f.model_dump() for f in findings], indent=2)}

Workspace: {workspace_path}
"""

        try:
            response = await client.query(
                system=system_prompt,
                message=user_message,
                max_tokens=8192,
                tools=["write_file", "run_command"],
            )

            content = response.get("content", "")

            fixes: dict[str, str] = {}
            try:
                data = json.loads(content)
                if "fixes" in data:
                    fixes = data["fixes"]
            except json.JSONDecodeError:
                fixes["fix_log"] = content

            return fixes

        except Exception as e:
            logger.error("fixer_error", error=str(e))
            raise


class ClaudeAgentSDKClient:
    """Adapter exposing a ``.query()`` over the real ``claude_agent_sdk``.

    All traffic is routed through ``ANTHROPIC_BASE_URL`` (injected per call via
    the SDK's subprocess env), so pointing it at the LiteLLM proxy makes the
    Claude Agent SDK talk to your OpenAI-compatible backend while still using
    the Anthropic wire format.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        # Import here so a missing/incompatible SDK falls back to mock cleanly
        # in AgentService._get_client.
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            TextBlock,
            query,
        )

        self._query = query
        self._Options = ClaudeAgentOptions
        self._AssistantMessage = AssistantMessage
        self._TextBlock = TextBlock
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    async def query(
        self,
        system: str,
        message: str,
        max_tokens: int = 4096,
        tools: list[str] | None = None,
    ) -> dict[str, str]:
        env: dict[str, str] = {}
        if self._base_url:
            env["ANTHROPIC_BASE_URL"] = self._base_url
        if self._api_key:
            env["ANTHROPIC_API_KEY"] = self._api_key

        options = self._Options(
            system_prompt=system,
            model=self._model or None,
            allowed_tools=[],  # planner/reviewer output is plain text; no tools
            permission_mode="bypassPermissions",
            max_turns=1,
            env=env,
        )

        parts: list[str] = []
        async for msg in self._query(prompt=message, options=options):
            if isinstance(msg, self._AssistantMessage):
                for block in msg.content:
                    if isinstance(block, self._TextBlock):
                        parts.append(block.text)
        return {"content": "".join(parts)}


class MockClaudeClient:
    """Deterministic offline stand-in for the Claude Agent SDK.

    It inspects the system prompt to determine which agent role is calling and
    returns role-appropriate, schema-valid JSON. This lets the entire job
    pipeline (planner -> builder -> reviewer -> fixer) run end-to-end without an
    API key, which is what the BACKEND handoff relies on for local testing.
    """

    async def query(
        self,
        system: str,
        message: str,
        max_tokens: int = 4096,
        tools: list[str] | None = None,
    ) -> dict[str, str]:
        await asyncio.sleep(0.05)
        role = self._detect_role(system)

        if role == "reviewer":
            return {"content": json.dumps(self._reviewer_response())}
        if role == "builder":
            return {"content": json.dumps(self._builder_response())}
        if role == "fixer":
            return {"content": json.dumps(self._fixer_response())}
        return {"content": json.dumps(self._planner_response())}

    @staticmethod
    def _detect_role(system: str) -> str:
        text = system.lower()
        if "code reviewer" in text:
            return "reviewer"
        if "fix issues found by the reviewer" in text:
            return "fixer"
        if "software architect" in text:
            return "planner"
        return "builder"

    @staticmethod
    def _planner_response() -> dict[str, Any]:
        # No follow-up questions: the finalized brief already contains everything
        # needed, so the job can proceed straight to generation.
        return {
            "app_type": "web_service",
            "stack": ["Python 3.12", "FastAPI"],
            "components": ["api", "service", "models"],
            "data_model": {},
            "api_boundaries": ["GET /", "GET /health"],
            "security_concerns": [],
            "assumptions": ["Generated in offline mock mode"],
            "risks": [],
            "deliverables": ["Runnable FastAPI application", "Basic tests"],
            "questions": [],
        }

    @staticmethod
    def _builder_response() -> dict[str, Any]:
        # A small, self-contained application. Intentionally omits a dependency
        # manifest so the review stage does not attempt a network install while
        # running offline.
        main_py = (
            "def add(a: int, b: int) -> int:\n"
            '    """Return the sum of two integers."""\n'
            "    return a + b\n\n\n"
            'def greeting(name: str = "world") -> str:\n'
            '    """Return a friendly greeting."""\n'
            '    return f"Hello, {name}!"\n\n\n'
            'if __name__ == "__main__":\n'
            "    print(greeting())\n"
        )
        test_py = (
            "from main import add, greeting\n\n\n"
            "def test_add() -> None:\n"
            "    assert add(2, 3) == 5\n\n\n"
            "def test_greeting() -> None:\n"
            '    assert greeting("FDE") == "Hello, FDE!"\n'
        )
        readme = (
            "# Generated Application\n\n"
            "This application was generated by APPDEVELOPER in offline mock mode.\n\n"
            "## Run\n\n"
            "```bash\npython main.py\n```\n\n"
            "## Test\n\n"
            "```bash\npytest\n```\n"
        )
        return {
            "files": {
                "main.py": main_py,
                "test_main.py": test_py,
                "README.md": readme,
            }
        }

    @staticmethod
    def _reviewer_response() -> dict[str, Any]:
        return {
            "findings": [],
            "commands_run": ["pytest -q"],
            "outcomes": {"pytest -q": True},
            "failed_tests": [],
            "risks": [],
            "review_rounds": 1,
            "passed": True,
        }

    @staticmethod
    def _fixer_response() -> dict[str, Any]:
        return {"fixes": {}}
