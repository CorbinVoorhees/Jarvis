"""status CHECK constraint on captures

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "captures_status_check",
        "captures",
        "status IN ('inbox', 'processed', 'archived')",
    )


def downgrade() -> None:
    op.drop_constraint("captures_status_check", "captures", type_="check")
