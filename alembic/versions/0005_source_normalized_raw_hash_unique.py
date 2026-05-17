"""Unique (source, normalized_raw_hash) for DB-backed ingestion dedup.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-16

Duplicate detection is exact per (source, normalized_raw_hash): re-ingesting the same
normalized payload under the same source always resolves to the existing row (HTTP 200).

Existing rows that share the same pair are deduplicated before adding the constraint:
the row with the smallest ``id`` per group is kept; others are deleted (local-dev scale).

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Deterministic: retain MIN(id) per (source, normalized_raw_hash); delete newer duplicates.
    conn.execute(
        text(
            "DELETE FROM captures AS c "
            "USING captures AS k "
            "WHERE c.source = k.source "
            "AND c.normalized_raw_hash = k.normalized_raw_hash "
            "AND c.id > k.id",
        ),
    )

    op.create_index(
        "uq_captures_source_normalized_raw_hash",
        "captures",
        ["source", "normalized_raw_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_captures_source_normalized_raw_hash", table_name="captures")
