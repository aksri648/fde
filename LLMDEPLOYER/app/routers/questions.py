from fastapi import APIRouter

from app.services.question_flow import get_questions

router = APIRouter()


@router.get("/questions")
async def list_questions():
    questions = get_questions()
    return {"questions": [q.model_dump() for q in questions]}
