"""Small parsing helpers shared by the rest of the package."""

from __future__ import annotations

import re
from typing import Any

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


KEY_RE = re.compile(r"^\s*#?\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*=\s*(.*)$")


COMMENT_RE = re.compile(r"^\s*#\s?(.*)$")


BOOLEAN_RE = re.compile(r"^(true|false)$", re.IGNORECASE)


NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _clean_value(raw: str) -> str:
    """Drop a trailing inline comment and surrounding whitespace."""
    value = raw.strip()
    if "#" in value:
        value = value.split("#", 1)[0]
    return value.strip()


def _infer_type(example: str) -> str:
    if BOOLEAN_RE.match(example or ""):
        return "boolean"
    if NUMBER_RE.match(example or ""):
        return "number"
    return "string"


def _default_example(kind: str) -> str:
    if kind == "boolean":
        return "True"
    if kind == "number":
        return "0"
    return '""'


def _pretty_label(key: str) -> str:
    """dxvk.enableGraphicsPipelineLibrary -> Enable Graphics Pipeline Library."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key)
    spaced = spaced.replace("_", " ")
    words = []
    for word in spaced.split():
        if word.isupper() and len(word) > 1:
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:].lower() if word else word)
    return " ".join(words)


def _has_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


_LABELS: dict[str, str] | None = None
