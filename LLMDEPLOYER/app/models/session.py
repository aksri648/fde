from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserRequirements(BaseModel):
    purpose: str
    concurrent_users: int
    peak_capacity: int
    business_context: str
    compliance: list[str]
    model_preference: str
    latency_requirements: str
    budget_constraints: str


class Session(BaseModel):
    session_id: str
    created_at: datetime
    status: str
    requirements: Optional[UserRequirements] = None
    deployment_result: Optional[dict] = None
    messages: list[dict] = []
