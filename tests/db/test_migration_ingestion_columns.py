"""Alembic 0004: normalized_raw_hash, external_id, partial unique."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.ingestion.dedup import normalized_raw_sha256_hex

pytestmark = pytest.mark.usefixtures("prepare_database")


def test_migration_0004_backfills_hash_and_keeps_existing_source():
    from app.db.session import get_engine

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    engine = get_engine()

    expected_hash = normalized_raw_sha256_hex("legacy row")

    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

        command.upgrade(cfg, "0003")

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO captures (type, title, content, question, "
                    "time, raw, source, status, updated_at) "
                    "VALUES ('task', 't', NULL, NULL, NULL, 'legacy row', 'api', 'inbox', now())",
                ),
            )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT normalized_raw_hash, external_id, source "
                    "FROM captures ORDER BY id LIMIT 1",
                ),
            ).one()
            assert row.source == "api"
            assert row.external_id is None
            assert row.normalized_raw_hash == expected_hash
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        command.upgrade(cfg, "head")
