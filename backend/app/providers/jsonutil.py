"""Lenient JSON extraction for model output."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from model output.

    Handles the usual deviations from "JSON only": markdown code fences and prose
    around the object. Raises ``ValueError`` if no object can be recovered.
    """
    text = _FENCE.sub("", raw.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in model output") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in model output: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data
