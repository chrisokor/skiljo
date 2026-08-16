import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TicketBatch(Base):
    __tablename__ = "ticket_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str | None] = mapped_column(Text)
    ticket_count: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TicketRecord(Base):
    __tablename__ = "ticket_records"
    __table_args__ = (Index("ix_ticket_records_batch_id_position", "batch_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ticket_batches.id"), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_versions.id"))
    source_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_versions.id"), nullable=False)
    ticket_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    summary: Mapped[dict | None] = mapped_column(JSONB)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str] = mapped_column(Text, nullable=False)
    matched_human_decision: Mapped[bool | None] = mapped_column()
    reasoning: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_calls.id"))


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column()
    cost_estimate_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    called_at: Mapped[datetime] = mapped_column(server_default=func.now())
    cached: Mapped[bool] = mapped_column(default=False, server_default="false")


class LLMCache(Base):
    __tablename__ = "llm_cache"

    cache_key: Mapped[str] = mapped_column(Text, primary_key=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    result_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(server_default=func.now())
