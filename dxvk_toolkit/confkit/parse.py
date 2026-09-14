"""Turning a reference dxvk.conf into the option model, and reading one back."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .base import COMMENT_RE, KEY_RE, SECTION_RE, _clean_value, _default_example, _infer_type
from .curate import _FORK_CONF
from .model import ConfModel, Member, OptionGroup


def _alias_group(key: str) -> list[str]:
    for group in KEY_ALIASES:
        if key in group:
            return list(group)
    return [key]


def parse_conf_text(text: str) -> tuple[dict[str, list[Member]], list[Member], list[str]]:
    """Parse the reference document into sections, an ordered list and order."""
    sections: dict[str, list[Member]] = {}
    ordered: list[Member] = []
    section_order: list[str] = []

    pending_comments: list[str] = []
    pending_raw: list[str] = []
    last_comments: list[str] = []
    last_raw: list[str] = []

    for line in text.splitlines():
        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip()
            if section not in section_order:
                section_order.append(section)
            pending_comments, pending_raw = [], []
            last_comments, last_raw = [], []
            continue

        key_match = KEY_RE.match(line)
        if key_match:
            section, key, raw_value = key_match.group(1), key_match.group(2), key_match.group(3)
            example = _clean_value(raw_value)
            kind = _infer_type(example)
            comment = " ".join(pending_comments if pending_comments else last_comments).strip()
            raw_lines = list(pending_raw if pending_raw else last_raw)
            raw_lines.append(line)
            member = Member(
                section=section,
                key=key,
                example=example or _default_example(kind),
                type=kind,
                comment=comment,
                raw_block="\n".join(raw_lines),
            )
            if section not in sections:
                sections[section] = []
                if section not in section_order:
                    section_order.append(section)
            sections[section].append(member)
            ordered.append(member)
            pending_comments, pending_raw = [], []
            continue

        comment_match = COMMENT_RE.match(line)
        if comment_match:
            pending_comments.append(comment_match.group(1).rstrip())
            pending_raw.append(line)
            # Remember the block so several commented keys in a row can share
            # the documentation that precedes them.
            last_comments = list(pending_comments)
            last_raw = list(pending_raw)
            continue

        if line.strip() == "":
            # Blank lines keep the pending comment block alive on purpose.
            continue

        pending_comments, pending_raw = [], []
        last_comments, last_raw = [], []

    return sections, ordered, section_order


def consolidate(ordered: Sequence[Member]) -> list[OptionGroup]:
    """Collapse repeated/aliased keys into one control per option."""
    groups: list[OptionGroup] = []
    used: set[int] = set()

    for index, member in enumerate(ordered):
        if index in used:
            continue
        aliases = _alias_group(member.key)
        same_doc = [
            other
            for other in ordered
            if other.key in aliases
            and (
                (not member.comment and not other.comment)
                or (member.comment and other.comment and member.comment == other.comment)
            )
        ]
        members: list[Member] = []
        kind = member.type
        example = member.example
        comment = member.comment
        for other in same_doc:
            position = ordered.index(other)
            if position in used:
                continue
            used.add(position)
            members.append(other)
            if kind != other.type:
                if {kind, other.type} == {"boolean", "number"}:
                    kind = "number"
                else:
                    kind = "string"
            if not example and other.example:
                example = other.example
            if not comment and other.comment:
                comment = other.comment
        groups.append(
            OptionGroup(
                key=member.key,
                members=members or [member],
                type=kind,
                example=example or _default_example(kind),
                comment=comment,
            )
        )
    return groups


def _fork_groups(existing: list["OptionGroup"]) -> list["OptionGroup"]:
    """Option groups that only the GPLAsync fork provides."""
    known = {group.key for group in existing}
    parsed = consolidate(parse_conf_text(_FORK_CONF)[1])
    return [group for group in parsed if group.key not in known]


def build_model(text: str, *, source: str = "", path: Path | None = None) -> ConfModel:
    sections, ordered, section_order = parse_conf_text(text)
    groups = consolidate(ordered)
    groups.extend(_fork_groups(groups))
    return ConfModel(
        source=source,
        source_path=path,
        sections=sections,
        ordered=ordered,
        section_order=section_order,
        groups=groups,
    )


def parse_config_values(text: str, model: "ConfModel") -> tuple[dict[str, Any], list[str]]:
    """Read an existing dxvk.conf and return the options it actually sets.

    Returns (values, unknown_keys). Commented lines and section headers are
    skipped; a boolean set to False is reported as not-set because the export
    side cannot express False either (an omitted line means the same thing).
    """
    known = {group.key: group for group in model.groups}
    values: dict[str, Any] = {}
    unknown: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if "=" not in line:
            continue
        key_part, _, value_part = line.partition("=")
        key_part = key_part.strip()
        if "." not in key_part:
            continue
        _section, _, key = key_part.rpartition(".")
        key = key.strip()
        value = value_part.strip()

        group = known.get(key)
        if group is None:
            if key:
                unknown.append(key_part)
            continue

        if group.type == "boolean":
            if value.strip('"').lower() in ("true", "1", "yes", "on"):
                values[key] = True
            continue

        cleaned = value
        if len(cleaned) >= 2 and cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned != "":
            values[key] = cleaned

    return values, unknown


KEY_ALIASES: tuple[tuple[str, ...], ...] = (
    ("syncInterval", "presentInterval"),
    ("maxFrameRate", "maxFrameRate"),
    ("maxFrameLatency", "maxFrameLatency"),
    ("enableHDR", "hdr"),
)
