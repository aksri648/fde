from pydantic import BaseModel, Field, SecretStr

from app.domain.enums import EventName


class FollowUpQuestion(BaseModel):
    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The follow-up question text")
    options: list[str] = Field(default_factory=list)
    required: bool = Field(default=True)


class ArchitectureProposal(BaseModel):
    app_type: str = Field(..., description="Type of application")
    stack: list[str] = Field(..., description="Technology stack")
    components: list[str] = Field(..., description="Main components")
    data_model: dict[str, str] = Field(default_factory=dict)
    api_boundaries: list[str] = Field(default_factory=list)
    security_concerns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    severity: str = Field(..., description="Error, Warning, or Info")
    evidence: str = Field(..., description="Evidence of the finding")
    affected_files: list[str] = Field(default_factory=list)
    required_fix: str = Field(..., description="Description of required fix")
    passed: bool = Field(default=False)


class ReviewReport(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    outcomes: dict[str, bool] = Field(default_factory=dict)
    failed_tests: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    review_rounds: int = Field(default=0)
    passed: bool = Field(default=False)


class JobCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=50000)


class JobResponse(BaseModel):
    job_id: str
    state: str
    brief: str | None = None
    questions: list[FollowUpQuestion] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)
    reports: list[ReviewReport] = Field(default_factory=list)
    artifact_count: int = 0


class AnswerSubmission(BaseModel):
    answers: dict[str, str] = Field(..., min_length=1)


class PushDecision(BaseModel):
    approved: bool


class GitHubPushRequest(BaseModel):
    repository_name: str = Field(..., pattern=r"^[a-zA-Z0-9._-]+$")
    visibility: str = Field(default="private", pattern=r"^(private|public)$")
    owner: str | None = None
    token: SecretStr
    confirm: bool = Field(default=False)


class GitHubPushResponse(BaseModel):
    html_url: str
    commit_sha: str
    repository_created: bool


class Event(BaseModel):
    name: EventName
    data: dict = Field(default_factory=dict)
    sequence: int = Field(..., ge=0)


class Snapshot(BaseModel):
    job_id: str
    state: str
    events: list[Event] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    database: bool
    configuration: bool
