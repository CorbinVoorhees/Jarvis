"""Alembic 0005: dedupe rows then unique (source, normalized_raw_hash)."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.ingestion.dedup import normalized_raw_sha256_hex

pytestmark = pytest.mark.usefixtures("prepare_database")


def test_migration_0005_deduplicates_before_unique_index():
    from app.db.session import get_engine

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    engine = get_engine()
    h = normalized_raw_sha256_hex("dup migration raw")

    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

        command.upgrade(cfg, "0004")

        with engine.begin() as conn:
            for title in ("first", "second"):
                conn.execute(
                    text(
                        "INSERT INTO captures (type, title, content, question, time, raw, source, "
                        "normalized_raw_hash, status, updated_at) "
                        "VALUES ('task', :title, NULL, NULL, NULL, 'dup migration raw', 'api', "
                        ":h, 'inbox', now())",
                    ),
                    {"title": title, "h": h},
                )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM captures WHERE normalized_raw_hash = :h"),
                {"h": h},
            ).scalar_one()
            assert n == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        command.upgrade(cfg, "head")
