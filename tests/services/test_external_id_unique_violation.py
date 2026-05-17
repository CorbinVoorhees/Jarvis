"""Unit tests for PostgreSQL IntegrityError classification (no database)."""

from sqlalchemy.exc import IntegrityError

from app.services.capture_service import (
    _external_id_unique_violation,
    _source_hash_unique_violation,
)


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


class _FakeDiagExternalNamed:
    constraint_name = "uq_captures_source_external_id"


class _FakeOrigExternalPg23505DiagNamedConstraint:
    pgcode = "23505"
    diag = _FakeDiagExternalNamed()


def test_external_id_violation_true_when_diag_constraint_name_set():
    exc = IntegrityError(None, None, _FakeOrigExternalPg23505DiagNamedConstraint())
    assert _external_id_unique_violation(exc) is True


class _FakeOrigWrongPgCode:
    pgcode = None
    diag = _FakeDiag()

    def __str__(self) -> str:
        return 'duplicate key violates "uq_captures_source_external_id"'


def test_external_id_unique_violation_false_without_pg_unique_violation_code():
    exc = IntegrityError(None, None, _FakeOrigWrongPgCode())
    assert _external_id_unique_violation(exc) is False


class _FakeDiagHashNamed:
    constraint_name = "uq_captures_source_normalized_raw_hash"


class _FakeOrigHashPg23505DiagNamedConstraint:
    pgcode = "23505"
    diag = _FakeDiagHashNamed()


def test_source_hash_violation_true_when_diag_constraint_name_set():
    exc = IntegrityError(None, None, _FakeOrigHashPg23505DiagNamedConstraint())
    assert _source_hash_unique_violation(exc) is True


class _FakeOrigHashPg23505DiagEmptyMessageNamesIndex:
    pgcode = "23505"
    diag = _FakeDiag()

    def __str__(self) -> str:
        return (
            'duplicate key value violates unique constraint '
            '"uq_captures_source_normalized_raw_hash"\nDETAIL: Key ...'
        )


def test_source_hash_violation_true_when_fallback_message_has_index():
    exc = IntegrityError(None, None, _FakeOrigHashPg23505DiagEmptyMessageNamesIndex())
    assert _source_hash_unique_violation(exc) is True


def test_source_hash_unique_violation_false_without_pg_unique_violation_code():
    exc = IntegrityError(None, None, _FakeOrigWrongPgCode())
    assert _source_hash_unique_violation(exc) is False
