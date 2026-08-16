"""ticket batches

Revision ID: a7b2c9d4e5f6
Revises: df49c1c3cda5
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b2c9d4e5f6"
down_revision = "df49c1c3cda5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("ticket_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "ticket_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ticket_batches.id"), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_data", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ticket_records")
    op.drop_table("ticket_batches")
