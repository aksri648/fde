from fastapi import HTTPException

from app.models.questions import Question
from app.models.session import UserRequirements


QUESTIONS: list[Question] = [
    Question(
        id="purpose",
        question="What is the purpose of this LLM deployment?",
        type="select",
        options=[
            "Agentic Coding",
            "General Usage",
            "Customer Support / Chatbot",
            "Internal Knowledge Base",
            "Content Generation",
            "Code Review & Analysis",
            "Other (please describe)",
        ],
    ),
    Question(
        id="concurrent_users",
        question="How many people will be using it simultaneously?",
        type="number",
        validation="Positive integer",
    ),
    Question(
        id="peak_capacity",
        question="What is the expected peak capacity of clients?",
        type="number",
        validation="Positive integer, must be >= simultaneous users",
    ),
    Question(
        id="business_context",
        question="Describe the business context for this deployment.",
        type="text",
        placeholder="e.g., We are a fintech startup needing to process customer queries...",
    ),
    Question(
        id="compliance",
        question="Are there any compliance requirements that need to be guaranteed?",
        type="multi_select",
        options=[
            "HIPAA",
            "SOC 2",
            "GDPR",
            "PCI DSS",
            "FedRAMP",
            "Data Residency (specify region)",
            "No specific compliance requirements",
            "Other (please describe)",
        ],
    ),
    Question(
        id="model_preference",
        question="Which LLM model do you prefer to deploy?",
        type="text",
        placeholder="e.g., Llama 3.1 70B, Qwen 2.5 72B, Mistral Large, etc.",
    ),
    Question(
        id="latency_requirements",
        question="What are your latency requirements?",
        type="select",
        options=[
            "Ultra-low (<100ms TTFT)",
            "Low (<500ms TTFT)",
            "Moderate (<2s TTFT)",
            "Flexible / Batch processing",
        ],
    ),
    Question(
        id="budget_constraints",
        question="What is your monthly budget range for this deployment?",
        type="select",
        options=[
            "< $500/month",
            "$500 - $2,000/month",
            "$2,000 - $10,000/month",
            "> $10,000/month",
            "Flexible / No hard limit",
        ],
    ),
]


def get_questions() -> list[Question]:
    return QUESTIONS


def compile_requirements(answers: dict) -> UserRequirements:
    errors = []
    for q in QUESTIONS:
        if q.required and q.id not in answers:
            errors.append(f"Missing required field: {q.id}")
        elif q.id in answers:
            val = answers[q.id]
            if q.type == "number":
                if not isinstance(val, int) or val <= 0:
                    errors.append(f"Field '{q.id}' must be a positive integer")
            if q.type == "multi_select" and not isinstance(val, list):
                errors.append(f"Field '{q.id}' must be a list")
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    return UserRequirements(
        purpose=answers["purpose"],
        concurrent_users=answers["concurrent_users"],
        peak_capacity=answers["peak_capacity"],
        business_context=answers["business_context"],
        compliance=answers.get("compliance", []),
        model_preference=answers["model_preference"],
        latency_requirements=answers["latency_requirements"],
        budget_constraints=answers["budget_constraints"],
    )
