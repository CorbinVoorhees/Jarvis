import json
import logging
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.config import get_settings
from app.core.exceptions import UpstreamParseError
from app.schemas.capture import ParsedCapture

logger = logging.getLogger(__name__)

_PARSE_SYSTEM = """You classify short user text into task, note, or question and extract fields.
Return ONLY valid JSON with keys: type ("task"|"note"|"question"), title, content,
question, time, raw.
- raw must echo the user's original text exactly as given.
- For type "task": set title to a concise task title; others null unless time is mentioned.
- For type "note": set content to the note body; title may be null.
- For type "question": set question to the question text.
- Use null for unused string fields. time is optional natural language time if present."""


def parse_capture_with_openai(raw_text: str, client: OpenAI | None = None) -> ParsedCapture:
    settings = get_settings()
    key = settings.openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    openai_client = client or OpenAI(api_key=key)
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM},
            {"role": "user", "content": raw_text},
        ],
    )
    text = response.choices[0].message.content
    if not text:
        logger.warning("Empty content in OpenAI completion response")
        raise UpstreamParseError("Empty response from upstream parse service")
    payload: dict[str, Any] = json.loads(text)
    payload["raw"] = raw_text
    try:
        return ParsedCapture.model_validate(payload)
    except ValidationError as e:
        logger.warning("OpenAI output failed ParsedCapture validation: %s", e.errors())
        raise UpstreamParseError("Upstream parse output failed validation") from e
