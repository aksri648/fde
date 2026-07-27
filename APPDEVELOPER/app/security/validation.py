import os
from pathlib import Path

from app.domain.schemas import JobResponse


def validate_workspace_path(
    workspace_root: str, job_id: str, requested_path: str
) -> str | None:
    root = Path(workspace_root).resolve()
    job_dir = root / job_id

    if not job_dir.exists():
        return None

    if os.path.isabs(requested_path):
        return None

    resolved = (job_dir / requested_path).resolve()

    if not str(resolved).startswith(str(job_dir.resolve())):
        return None

    try:
        resolved.relative_to(job_dir)
    except ValueError:
        return None

    if resolved.is_symlink():
        real_target = resolved.resolve()
        if not str(real_target).startswith(str(job_dir.resolve())):
            return None

    return str(resolved)


def sanitize_job_response(job: JobResponse) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        state=job.state,
        brief=job.brief,
        questions=job.questions,
        answers=job.answers,
        reports=job.reports,
        artifact_count=job.artifact_count,
    )
