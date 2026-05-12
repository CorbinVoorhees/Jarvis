"""capture status and updated_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'inbox'"),
            nullable=False,
        ),
    )
    op.add_column(
        "captures",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(sa.text("UPDATE captures SET updated_at = created_at"))


def downgrade() -> None:
    op.drop_column("captures", "updated_at")
    op.drop_column("captures", "status")
