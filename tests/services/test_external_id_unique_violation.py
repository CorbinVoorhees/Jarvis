"""Unit tests for external_id IntegrityError classification (no database)."""

from sqlalchemy.exc import IntegrityError

from app.services.capture_service import _external_id_unique_violation


class _FakeDiag:
    constraint_name = None


class _FakeOrigPg23505DiagEmptyMessageNamesIndex:
    """Simulates psycopg leaving constraint_name unset but embedding the index in the message."""

    pgcode = "23505"
    diag = _FakeDiag()

    def __str__(self) -> str:
        return (
            'duplicate key value violates unique constraint "uq_captures_source_external_id"\n'
            "DETAIL: Key ..."
        )


def test_external_id_violation_true_when_fallback_message_has_index():
    exc = IntegrityError(None, None, _FakeOrigPg23505DiagEmptyMessageNamesIndex())
    assert _external_id_unique_violation(exc) is True


class _FakeOrigWrongPgCode:
    pgcode = None
    diag = _FakeDiag()

    def __str__(self) -> str:
        return 'duplicate key violates "uq_captures_source_external_id"'


def test_external_id_unique_violation_false_without_pg_unique_violation_code():
    exc = IntegrityError(None, None, _FakeOrigWrongPgCode())
    assert _external_id_unique_violation(exc) is False
