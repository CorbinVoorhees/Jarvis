"""Tests for raw normalization prior to ingestion hashing."""

from app.ingestion.dedup import normalize_raw_for_dedup, normalized_raw_sha256_hex


def test_normalize_trims_collapses_spaces_and_lowercases():
    assert normalize_raw_for_dedup("  HELLO\t  world ") == "hello world"


def test_equivalent_strings_share_hash():
    a = normalized_raw_sha256_hex("FOO   BAR")
    b = normalized_raw_sha256_hex("  foo bar  ")
    assert a == b
