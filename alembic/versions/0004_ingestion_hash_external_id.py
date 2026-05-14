"""ingestion dedup hash, external id, indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column(
            "normalized_raw_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "captures",
        sa.Column("external_id", sa.String(length=512), nullable=True),
    )

    conn = op.get_bind()
    from app.ingestion.dedup import normalized_raw_sha256_hex

    # Row-by-row Python hashing avoids a pgcrypto dependency; suited to modest captures row counts.

    rows = conn.execute(text("SELECT id, raw FROM captures")).mappings().all()
    for r in rows:
        h = normalized_raw_sha256_hex(r["raw"])
        conn.execute(
            text(
                "UPDATE captures SET normalized_raw_hash = :h WHERE id = :id",
            ),
            {"h": h, "id": r["id"]},
        )

    op.alter_column(
        "captures",
        "normalized_raw_hash",
        nullable=False,
    )

    # CHECK runs after nullable hash is populated; legacy rows remain source=api (migration 0001),
    # so enforcing allowed values cannot fail existing data.

    op.create_check_constraint(
        "captures_source_values_check",
        "captures",
        "source IN ('api', 'sms', 'voice', 'email', 'manual')",
    )

    op.create_index(
        "ix_captures_dedup_lookup",
        "captures",
        ["source", "normalized_raw_hash", "created_at"],
        unique=False,
    )

    op.create_index(
        "uq_captures_source_external_id",
        "captures",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_captures_source_external_id", table_name="captures")
    op.drop_index("ix_captures_dedup_lookup", table_name="captures")
    op.drop_constraint("captures_source_values_check", "captures", type_="check")
    op.drop_column("captures", "external_id")
    op.drop_column("captures", "normalized_raw_hash")
