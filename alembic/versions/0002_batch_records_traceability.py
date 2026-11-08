"""Add batch_records append-only traceability table

Revision ID: 0002_batch_records_traceability
Revises: 0001_initial_kb_schema
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_batch_records_traceability"
down_revision: Union[str, None] = "0001_initial_kb_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch_records",
        sa.Column("batch_code", sa.String(length=64), primary_key=True),
        sa.Column("commodity", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.String(length=64), nullable=False),
        sa.Column("harvest_or_production_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("packaging_used", sa.String(length=255), nullable=False),
        sa.Column("result_id", sa.String(length=64), nullable=False),
        sa.Column("packer_identity", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column(
            "handling_events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("ix_batch_records_created_at", "batch_records", ["created_at"])
    op.create_index("ix_batch_records_result_id", "batch_records", ["result_id"])


def downgrade() -> None:
    op.drop_index("ix_batch_records_result_id", table_name="batch_records")
    op.drop_index("ix_batch_records_created_at", table_name="batch_records")
    op.drop_table("batch_records")
