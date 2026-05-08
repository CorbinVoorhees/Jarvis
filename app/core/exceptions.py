class JarvisError(Exception):
    """Base exception for Jarvis."""


class UpstreamParseError(JarvisError):
    """Raised when an upstream model/service returns unusable output."""