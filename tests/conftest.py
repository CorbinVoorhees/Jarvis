import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://jarvis:jarvis@127.0.0.1:5432/jarvis",
)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used-when-mocked")


@pytest.fixture(scope="session")
def prepare_database():
    from app.config import get_settings

    get_settings.cache_clear()

    from app.db.session import configure_db, get_engine, reset_db_engine

    reset_db_engine()
    configure_db()
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS captures CASCADE"))

    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def clean_captures_table(prepare_database):
    from app.db.session import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE TABLE captures RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
