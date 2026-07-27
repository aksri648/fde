import json

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.domain.enums import JobState


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    prompt = Column(Text, nullable=False)
    state = Column(String(30), nullable=False, default=JobState.CREATED)
    brief = Column(Text, nullable=True)
    questions = Column(Text, nullable=True, default="[]")
    answers = Column(Text, nullable=True, default="{}")
    reports = Column(Text, nullable=True, default="[]")
    artifact_count = Column(Integer, nullable=False, default=0)
    review_rounds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def get_questions(self) -> list[dict]:
        return json.loads(self.questions or "[]")

    def get_answers(self) -> dict[str, str]:
        return json.loads(self.answers or "{}")

    def get_reports(self) -> list[dict]:
        return json.loads(self.reports or "[]")

    def set_questions(self, questions: list[dict]) -> None:
        self.questions = json.dumps(questions)

    def set_answers(self, answers: dict[str, str]) -> None:
        self.answers = json.dumps(answers)

    def set_reports(self, reports: list[dict]) -> None:
        self.reports = json.dumps(reports)


class EventRow(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    data = Column(Text, nullable=False, default="{}")
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def get_data(self) -> dict:
        return json.loads(self.data or "{}")

    def set_data(self, data: dict) -> None:
        self.data = json.dumps(data)


class Database:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self) -> AsyncSession:
        return self._session_factory()

    async def dispose(self) -> None:
        await self._engine.dispose()
