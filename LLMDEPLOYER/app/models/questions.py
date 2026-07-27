from typing import Optional
from pydantic import BaseModel


class Question(BaseModel):
    id: str
    question: str
    type: str
    options: Optional[list[str]] = None
    placeholder: Optional[str] = None
    validation: Optional[str] = None
    required: bool = True
