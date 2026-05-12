"""Alembic 0002: status + updated_at backfill on legacy schema."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command

pytestmark = pytest.mark.usefixtures("prepare_database")


def test_migration_backfills_existing_rows_as_inbox_and_syncs_updated_at():
    from app.db.session import get_engine

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    engine = get_engine()

    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

        command.upgrade(cfg, "0001")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO captures (type, title, content, question, time, raw, source) "
                    "VALUES ('task', 't', NULL, NULL, NULL, 'legacy', 'api')"
                )
            )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, updated_at, created_at FROM captures "
                    "ORDER BY id ASC LIMIT 1"
                )
            ).one()
            assert row.status == "inbox"
            assert row.updated_at == row.created_at
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        command.upgrade(cfg, "head")
