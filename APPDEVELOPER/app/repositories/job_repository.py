from sqlalchemy import select, update

from app.db.models import Database, EventRow, JobRow
from app.domain.enums import EventName, JobState


class JobRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, job_id: str, prompt: str) -> JobRow:
        async with self._db.get_session() as session:
            job = JobRow(id=job_id, prompt=prompt, state=JobState.CREATED)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def get(self, job_id: str) -> JobRow | None:
        async with self._db.get_session() as session:
            result = await session.execute(select(JobRow).where(JobRow.id == job_id))
            return result.scalar_one_or_none()

    async def update_state(self, job_id: str, state: JobState) -> None:
        async with self._db.get_session() as session:
            await session.execute(
                update(JobRow).where(JobRow.id == job_id).values(state=state)
            )
            await session.commit()

    async def update_brief(self, job_id: str, brief: str) -> None:
        async with self._db.get_session() as session:
            await session.execute(
                update(JobRow).where(JobRow.id == job_id).values(brief=brief)
            )
            await session.commit()

    async def update_questions(self, job_id: str, questions: list[dict]) -> None:
        async with self._db.get_session() as session:
            job = await session.execute(select(JobRow).where(JobRow.id == job_id))
            job_row = job.scalar_one()
            job_row.set_questions(questions)
            await session.commit()

    async def update_answers(self, job_id: str, answers: dict[str, str]) -> None:
        async with self._db.get_session() as session:
            job = await session.execute(select(JobRow).where(JobRow.id == job_id))
            job_row = job.scalar_one()
            job_row.set_answers(answers)
            await session.commit()

    async def update_reports(self, job_id: str, reports: list[dict]) -> None:
        async with self._db.get_session() as session:
            job = await session.execute(select(JobRow).where(JobRow.id == job_id))
            job_row = job.scalar_one()
            job_row.set_reports(reports)
            await session.commit()

    async def update_artifact_count(self, job_id: str, count: int) -> None:
        async with self._db.get_session() as session:
            await session.execute(
                update(JobRow).where(JobRow.id == job_id).values(artifact_count=count)
            )
            await session.commit()

    async def update_review_rounds(self, job_id: str, rounds: int) -> None:
        async with self._db.get_session() as session:
            await session.execute(
                update(JobRow).where(JobRow.id == job_id).values(review_rounds=rounds)
            )
            await session.commit()

    async def list_all(self) -> list[JobRow]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(JobRow).order_by(JobRow.created_at.desc())
            )
            return list(result.scalars().all())


class EventRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self, job_id: str, name: EventName, data: dict, sequence: int
    ) -> EventRow:
        async with self._db.get_session() as session:
            event = EventRow(job_id=job_id, name=name, sequence=sequence)
            event.set_data(data)
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    async def list_for_job(self, job_id: str) -> list[EventRow]:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(EventRow)
                .where(EventRow.job_id == job_id)
                .order_by(EventRow.sequence)
            )
            return list(result.scalars().all())

    async def get_max_sequence(self, job_id: str) -> int:
        async with self._db.get_session() as session:
            result = await session.execute(
                select(EventRow.sequence)
                .where(EventRow.job_id == job_id)
                .order_by(EventRow.sequence.desc())
                .limit(1)
            )
            row = result.first()
            return row[0] if row else 0
