from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.domain.schemas import (
    AnswerSubmission,
    GitHubPushRequest,
    GitHubPushResponse,
    JobCreate,
    JobResponse,
    PushDecision,
)
from app.security.auth import verify_api_key
from app.services.job_service import JobService

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreate,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> JobResponse:
    try:
        job = await job_service.create_job(request)
        # Advance the job through architecture + generation in the background so
        # a caller (e.g. the BACKEND handoff) that only creates the job still
        # gets a fully generated, reviewed codebase.
        background_tasks.add_task(job_service.run_pipeline, job.job_id)
        return job
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> JobResponse:
    try:
        return await job_service.get_job(job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{job_id}/answers", response_model=JobResponse)
async def submit_answers(
    job_id: str,
    request: AnswerSubmission,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> JobResponse:
    try:
        result = await job_service.submit_answers(job_id, request.answers)
        # If answering the questions finalized the brief, auto-start generation.
        if result.state == "READY_TO_GENERATE":
            background_tasks.add_task(job_service.generate_safe, job_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{job_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate(
    job_id: str,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> dict[str, str]:
    try:
        background_tasks.add_task(job_service.generate, job_id)
        return {"message": "Generation started", "job_id": job_id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{job_id}/artifacts")
async def list_artifacts(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> dict[str, list[str]]:
    try:
        await job_service.get_job(job_id)
        return {"artifacts": job_service._workspace.list_files(job_id)}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{job_id}/artifacts/{file_path:path}")
async def get_artifact(
    job_id: str,
    file_path: str,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> dict[str, str]:
    try:
        await job_service.get_job(job_id)
        content = job_service._workspace.read_file(job_id, file_path)
        return {"content": content}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{job_id}/push-decision", response_model=JobResponse)
async def push_decision(
    job_id: str,
    request: PushDecision,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> JobResponse:
    try:
        return await job_service.push_decision(job_id, request.approved)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{job_id}/github/push", response_model=GitHubPushResponse)
async def push_to_github(
    job_id: str,
    request: GitHubPushRequest,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> GitHubPushResponse:
    try:
        return await job_service.push_to_github(job_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    _: str = Depends(verify_api_key),
) -> JobResponse:
    try:
        return await job_service.cancel(job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
