from enum import StrEnum


class CaptureSource(StrEnum):
    API = "api"
    SMS = "sms"
    VOICE = "voice"
    EMAIL = "email"
    MANUAL = "manual"


class CaptureStatus(StrEnum):
    INBOX = "inbox"
    PROCESSED = "processed"
    ARCHIVED = "archived"
