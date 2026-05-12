from enum import StrEnum


class CaptureStatus(StrEnum):
    INBOX = "inbox"
    PROCESSED = "processed"
    ARCHIVED = "archived"
