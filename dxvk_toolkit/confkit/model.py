"""The option model: one entry per configurable option."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BOOLEAN_RE, COMMENT_RE, NUMBER_RE, _default_example, _has_value, _pretty_label
from .curate import BASIC_KEYS
from .i18n import documentation_overrides, label_overrides


@dataclass
class Member:
    """One concrete section.key line found in the reference file."""

    section: str
    key: str
    example: str
    type: str
    comment: str
    raw_block: str = ""

    @property
    def qualified(self) -> str:
        return f"{self.section}.{self.key}"

    @property
    def quoted_example(self) -> bool:
        """True when the reference file writes this value inside quotes."""
        text = (self.example or "").strip()
        return len(text) >= 2 and text.startswith('"') and text.endswith('"')

    @property
    def bare_example(self) -> bool:
        """True for unquoted, non-numeric examples such as Auto or 12_1."""
        text = (self.example or "").strip()
        if not text or self.quoted_example or NUMBER_RE.match(text):
            return False
        return BOOLEAN_RE.match(text) is None

    def description_text(self) -> str:
        """Human readable documentation: comments first, then the key line."""
        comments: list[str] = []
        key_lines: list[str] = []
        for line in (self.raw_block or "").splitlines():
            match = COMMENT_RE.match(line)
            if match:
                comments.append(match.group(1).rstrip())
                continue
            stripped = line.strip()
            if stripped:
                key_lines.append(stripped)
        if not comments and self.comment:
            comments = [self.comment]
        if not key_lines and self.example:
            key_lines = [f"{self.qualified} = {self.example}"]
        text = "\n".join(comments).strip()
        if key_lines:
            text = (text + "\n\n" if text else "") + "\n".join(key_lines)
        return text.strip()


@dataclass
class OptionGroup:
    """All sections that expose the same option, as one UI control."""

    key: str
    members: list[Member]
    type: str
    example: str
    comment: str

    @property
    def label(self) -> str:
        text = label_overrides().get(self.key) or _pretty_label(self.key)
        names = self.section_names
        return f"{text}  ({names})" if len(self.members) > 1 else text

    @property
    def section_names(self) -> str:
        seen: list[str] = []
        for member in self.members:
            if member.section not in seen:
                seen.append(member.section)
        return ", ".join(seen)

    @property
    def sections(self) -> list[str]:
        return [member.section for member in self.members]

    def summary(self, limit: int = 320) -> str:
        """The documentation as one readable paragraph (for inline display).

        Chinese when a translation exists, English otherwise.
        """
        translated = documentation_overrides().get(self.key, "")
        if translated:
            return translated
        return self.summary_en(limit)

    def summary_en(self, limit: int = 320) -> str:
        """The original English documentation, always available.

        DXVK documents every option in the comment block above it inside its
        own dxvk.conf, which is the authoritative description - the upstream
        wiki does not cover the individual keys.
        """
        parts: list[str] = []
        for member in self.members:
            for line in (member.raw_block or "").splitlines():
                match = COMMENT_RE.match(line)
                if not match:
                    continue
                text = " ".join(match.group(1).split())
                if text and text not in parts:
                    parts.append(text)
        joined = " ".join(parts).strip()
        if not joined:
            joined = self.comment.strip()
        return joined[:limit] + ("…" if len(joined) > limit else "")

    def doc_parts(self) -> tuple[str, str, str]:
        """The documentation split for a sectioned doc card: (说明, 示例, 原文).

        说明 is the curated Chinese text when a translation exists; 原文 is the
        raw English block from dxvk.conf and is always available. Callers lay
        the three parts out as separate visual sections instead of one blob.
        """
        translated = documentation_overrides().get(self.key, "")
        example = " | ".join(
            f"{member.qualified} = {member.example or _default_example(self.type)}"
            for member in self.members
        )
        original = self.description_en()
        return (translated, example, original)

    def tooltip(self) -> str:
        """Full documentation for a hover tooltip: Chinese, example, English."""
        translated, example, original = self.doc_parts()
        parts: list[str] = []
        if translated:
            parts.append(translated)
        parts.append(f"示例：{example}")
        if translated and original:
            parts.append("【DXVK 原文】\n" + original)
        elif original:
            parts.append(original)
        return "\n\n".join(part for part in parts if part.strip())

    def description_en(self) -> str:
        """The raw English documentation block from dxvk.conf."""
        blocks: list[str] = []
        for member in self.members:
            text = member.description_text()
            if text and text not in blocks:
                blocks.append(text)
        example = " | ".join(
            f"{member.qualified} = {member.example or _default_example(self.type)}"
            for member in self.members
        )
        body = "\n\n".join(blocks)
        return (body + "\n\n" if body else "") + f"Example: {example}"

    def description(self) -> str:
        """Alias for the English documentation (older callers use this name)."""
        return self.description_en()

    @property
    def prefers_bare(self) -> bool:
        """Whether values should be written without quotes.

        DXVK drops the quotes when parsing, so both forms work, but mirroring
        the reference file (Auto, 12_1, 10DE, ...) keeps generated files
        looking exactly like upstream's own examples.
        """
        return self.type == "string" and any(member.bare_example for member in self.members)

    def default_value(self) -> Any:
        if self.type == "boolean":
            return False
        if self.type == "number":
            return NUMBER_RE.match(self.example or "") and self.example or "0"
        return ""

    def matches(self, needle: str) -> bool:
        if not needle:
            return True
        haystack = " ".join(
            [self.key, self.label, self.comment, self.section_names]
            + [member.description_text() for member in self.members]
        ).lower()
        return needle.lower() in haystack


@dataclass
class ConfModel:
    """Parsed option catalogue."""

    source: str = ""
    source_path: Path | None = None
    sections: dict[str, list[Member]] = field(default_factory=dict)
    ordered: list[Member] = field(default_factory=list)
    section_order: list[str] = field(default_factory=list)
    groups: list[OptionGroup] = field(default_factory=list)

    @property
    def option_count(self) -> int:
        return len(self.groups)

    def filter(
        self,
        needle: str = "",
        *,
        basic_only: bool = False,
        current: dict[str, Any] | None = None,
    ) -> list[OptionGroup]:
        """Groups matching the search text, optionally limited to basic keys.

        Options the user already touched stay visible even in basic mode so a
        selection never silently disappears.
        """
        chosen: list[OptionGroup] = []
        for group in self.groups:
            if basic_only and group.key not in BASIC_KEYS:
                if not (current and _has_value(current.get(group.key))):
                    continue
            if needle and not group.matches(needle):
                continue
            chosen.append(group)
        return chosen
