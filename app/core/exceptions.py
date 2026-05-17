class JarvisError(Exception):
    """Base exception for Jarvis."""


class UpstreamParseError(JarvisError):
    """Raised when an upstream model/service returns unusable output."""


class CaptureUpdateInvariantViolation(JarvisError):
    """Patch update used disallowed column keys; internal programming error path."""

    __slots__ = ("invalid_keys",)

    def __init__(self, invalid_keys: set[str]):
        self.invalid_keys = frozenset(invalid_keys)
        super().__init__("illegal patch column keys")


class ExternalIdConflictError(JarvisError):
    """Duplicate (source, external_id) violates DB uniqueness."""


class DuplicateRawHashConflictError(JarvisError):
    """Insert lost a race to another row with the same (source, normalized_raw_hash)."""

    __slots__ = ("existing",)

    def __init__(self, existing: object):
        self.existing = existing
        super().__init__("duplicate normalized raw hash for source")