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