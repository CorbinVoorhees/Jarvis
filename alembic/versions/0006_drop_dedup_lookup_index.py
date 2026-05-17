"""Drop redundant ix_captures_dedup_lookup.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-16

``uq_captures_source_normalized_raw_hash`` is sufficient for lookups by
(source, normalized_raw_hash); the older non-unique index is redundant.

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_captures_dedup_lookup", table_name="captures")


def downgrade() -> None:
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_captures_dedup_lookup "
            "ON captures (source, normalized_raw_hash, created_at)",
        ),
    )
