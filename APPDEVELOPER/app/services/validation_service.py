from dataclasses import dataclass, field

import structlog

from app.services.workspace_service import WorkspaceService

logger = structlog.get_logger()

SERVICE_COMMANDS = [
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["mypy", "app"],
    ["bandit", "-q", "-r", "app"],
    ["pytest", "-q", "--cov=app", "--cov-fail-under=80"],
]

INFERENCE_RULES = {
    "pyproject.toml": {
        "install": ["pip", "install", "-e", ".[dev]"],
        "test": ["pytest", "-q"],
        "lint": ["ruff", "check", "."],
        "format": ["ruff", "format", "--check", "."],
        "typecheck": ["mypy", "."],
    },
    "requirements.txt": {
        "install": ["pip", "install", "-r", "requirements.txt"],
        "test": ["pytest", "-q"],
    },
    "package.json": {
        "install": ["npm", "install"],
        "test": ["npm", "test"],
        "lint": ["npm", "run", "lint"],
        "build": ["npm", "run", "build"],
    },
    "Cargo.toml": {
        "install": ["cargo", "build"],
        "test": ["cargo", "test"],
        "lint": ["cargo", "clippy"],
    },
}


@dataclass
class ValidationResult:
    command: str
    passed: bool
    output: str
    exit_code: int


@dataclass
class ValidationReport:
    results: list[ValidationResult] = field(default_factory=list)
    all_passed: bool = True

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)
        if not result.passed:
            self.all_passed = False

    def to_dict(self) -> dict:
        return {
            "results": [
                {
                    "command": r.command,
                    "passed": r.passed,
                    "output": r.output[:1000],
                    "exit_code": r.exit_code,
                }
                for r in self.results
            ],
            "all_passed": self.all_passed,
        }


class ValidationService:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self._workspace = workspace_service

    async def validate_service(self, job_id: str) -> ValidationReport:
        report = ValidationReport()
        workspace_path = self._workspace.get_workspace_path(job_id)

        for cmd in SERVICE_COMMANDS:
            cmd_str = " ".join(cmd)
            try:
                exit_code, stdout, stderr = await self._workspace.run_subprocess(
                    cmd, workspace_path
                )
                output = stdout + stderr
                result = ValidationResult(
                    command=cmd_str,
                    passed=exit_code == 0,
                    output=output,
                    exit_code=exit_code,
                )
                report.add(result)
                logger.info(
                    "validation_command",
                    job_id=job_id,
                    command=cmd_str,
                    passed=exit_code == 0,
                )
            except Exception as e:
                result = ValidationResult(
                    command=cmd_str,
                    passed=False,
                    output=str(e),
                    exit_code=-1,
                )
                report.add(result)
                logger.error(
                    "validation_error",
                    job_id=job_id,
                    command=cmd_str,
                    error=str(e),
                )

        return report

    async def validate_generated_app(self, job_id: str) -> ValidationReport:
        report = ValidationReport()
        workspace_path = self._workspace.get_workspace_path(job_id)

        manifest_files = [
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "Cargo.toml",
        ]

        detected_manifest = None
        for manifest in manifest_files:
            try:
                self._workspace.read_file(job_id, manifest)
                detected_manifest = manifest
                break
            except FileNotFoundError:
                continue

        if detected_manifest is None:
            logger.warning("no_manifest_found", job_id=job_id)
            return report

        commands = INFERENCE_RULES.get(detected_manifest, {})

        if "install" in commands:
            cmd = commands["install"]
            try:
                exit_code, stdout, stderr = await self._workspace.run_subprocess(
                    cmd, workspace_path, timeout=600
                )
                result = ValidationResult(
                    command=" ".join(cmd),
                    passed=exit_code == 0,
                    output=stdout + stderr,
                    exit_code=exit_code,
                )
                report.add(result)
            except Exception as e:
                result = ValidationResult(
                    command=" ".join(cmd),
                    passed=False,
                    output=str(e),
                    exit_code=-1,
                )
                report.add(result)

        for step_name, cmd in commands.items():
            if step_name == "install":
                continue
            try:
                exit_code, stdout, stderr = await self._workspace.run_subprocess(
                    cmd, workspace_path
                )
                result = ValidationResult(
                    command=" ".join(cmd),
                    passed=exit_code == 0,
                    output=stdout + stderr,
                    exit_code=exit_code,
                )
                report.add(result)
            except Exception as e:
                result = ValidationResult(
                    command=" ".join(cmd),
                    passed=False,
                    output=str(e),
                    exit_code=-1,
                )
                report.add(result)

        return report
