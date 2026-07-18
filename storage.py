"""Persistence boundary for TraceLens.

Replace ``TraceStorage`` with another implementation to move from SQLite to a
different backend without changing the API routes.
"""

from datetime import datetime
from sqlalchemy import DateTime, Float, JSON, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from schemas import TraceEvent


class Base(DeclarativeBase):
    pass


class TraceEventRecord(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String, nullable=False)
    step_type: Mapped[str] = mapped_column(String, nullable=False)
    input_payload: Mapped[dict] = mapped_column("input", JSON, nullable=False)
    output_payload: Mapped[dict] = mapped_column("output", JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    parent_step_id: Mapped[str | None] = mapped_column(String, nullable=True)


class TraceStorage:
    """SQLite implementation of the trace event storage interface."""

    def __init__(self, database_url: str = "sqlite:///./tracelens.db") -> None:
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    def is_empty(self) -> bool:
        """Return whether this backend contains no stored trace events."""
        statement = select(TraceEventRecord.id).limit(1)
        with self.session_factory() as session:
            return session.scalar(statement) is None

    def store(self, event: TraceEvent) -> TraceEvent:
        record = TraceEventRecord(
            agent_id=event.agent_id,
            run_id=event.run_id,
            step_id=event.step_id,
            step_type=event.step_type,
            input_payload=event.input,
            output_payload=event.output,
            timestamp=event.timestamp,
            latency_ms=event.latency_ms,
            status=event.status,
            parent_step_id=event.parent_step_id,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_event(record)

    def get_run_events(self, run_id: str) -> list[TraceEvent]:
        statement = (
            select(TraceEventRecord)
            .where(TraceEventRecord.run_id == run_id)
            .order_by(TraceEventRecord.timestamp, TraceEventRecord.id)
        )
        with self.session_factory() as session:
            records = session.scalars(statement).all()
            return [self._to_event(record) for record in records]

    @staticmethod
    def _to_event(record: TraceEventRecord) -> TraceEvent:
        return TraceEvent(
            agent_id=record.agent_id,
            run_id=record.run_id,
            step_id=record.step_id,
            step_type=record.step_type,
            input=record.input_payload,
            output=record.output_payload,
            timestamp=record.timestamp,
            latency_ms=record.latency_ms,
            status=record.status,
            parent_step_id=record.parent_step_id,
        )


storage = TraceStorage()
