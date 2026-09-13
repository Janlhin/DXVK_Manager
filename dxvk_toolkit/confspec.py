"""Turn a reference dxvk.conf into a UI-ready option model.

DXVK ships its configuration reference as a heavily commented dxvk.conf: every
option appears as a commented or live "section.key = value" line preceded by
the documentation for that option. That file is the single source of truth
here - whatever version of it is used, the generated UI follows it, so new
DXVK options show up without touching this code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .paths import asset_path, settings
from .sources import list_installed, reference_conf

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KEY_RE = re.compile(r"^\s*#?\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*=\s*(.*)$")
COMMENT_RE = re.compile(r"^\s*#\s?(.*)$")
BOOLEAN_RE = re.compile(r"^(true|false)$", re.IGNORECASE)
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

# Options shown while "basic" mode is on. Everything else stays available
# under "advanced". The list is intentionally short and hand-picked for the
# settings people actually change (frame limits, sync, HUD, HDR, async).
BASIC_KEYS = (
    # frame pacing and sync
    "maxFrameRate",
    "syncInterval",
    "presentInterval",
    "maxFrameLatency",
    "tearFree",
    # picture and output
    "enableHDR",
    "hdr",
    "samplerAnisotropy",
    "samplerLodBias",
    # performance switches people actually flip
    "numCompilerThreads",
    "enableGraphicsPipelineLibrary",
    "enableAsync",
    "maxFeatureLevel",
    # multi-GPU and compatibility
    "deviceFilter",
    "deferSurfaceCreation",
    # on-screen display
    "hud",
)

# Options hidden from "advanced" mode: they only matter for Direct3D 8 titles,
# reproduce another vendor's bugs, or are driver workarounds nobody flips by
# accident. "full" mode still lists them.
LEGACY_KEYS = (
    "supportX4R4G4B4",
    "disableA8RT",
    "placeP8InScratch",
    "forceLegacyBuffers",
    "shadowPerspectiveDivide",
    "scaleDref",
    "floatEmulation",
    "lowerSinCos",
    "memoryTrackTest",
    "useD32forD24",
    "supportDFFormats",
    "disableDirectImageMapping",
    "reproducibleCommandStream",
    "enableDebugUtils",
    "countLosableResources",
    "deviceLossOnFocusLoss",
    "maxAvailableMemory",
    "forceVsDecl",
)

# Options that exist only in the DXVK-GPLAsync fork. Source: the fork's patch
# set (dxvk.enableAsync, dxvk.gplAsyncCache) plus its README; upstream's
# dxvk.conf does not contain them, which is why the catalogue used to list
# enableAsync in BASIC_KEYS yet never show it.
GPLASYNC_ONLY: dict[str, dict[str, str]] = {
    "enableAsync": {
        "label": "异步着色器编译",
        "summary": "GPLAsync 专有：在后台线程编译着色器，减少首次进入新场景的卡顿；"
                   "代价是可能出现贴图短暂弹出。官方 DXVK 无此选项。",
        "example": "True",
        "section": "dxvk",
        "tier": "simple",
    },
    "gplAsyncCache": {
        "label": "状态缓存配合 GPL",
        "summary": "GPLAsync 专有：让状态缓存与图形管线库配合工作；"
                   "该分支 v2.7-1 起已移除，仅旧版本需要。",
        "example": "True",
        "section": "dxvk",
        "tier": "advanced",
    },
}


def build_of(key: str) -> str:
    """Which build an option belongs to: "gplasync" or "both"."""
    return "gplasync" if key in GPLASYNC_ONLY else "both"


MODES = ("simple", "advanced", "full")

# "simple" mode groups by what an option is FOR, not by which section it lives
# in: one option can appear in dxvk, dxgi and d3d9 at once, so section headers
# only make sense in the technical modes.
PURPOSE_ORDER = ("帧率与同步", "画面与输出", "性能优化", "兼容性", "显示与诊断", "其他")
PURPOSE: dict[str, str] = {
    "maxFrameRate": "帧率与同步",
    "syncInterval": "帧率与同步",
    "presentInterval": "帧率与同步",
    "maxFrameLatency": "帧率与同步",
    "tearFree": "帧率与同步",
    "latencySleep": "帧率与同步",
    "latencyTolerance": "帧率与同步",
    "enableHDR": "画面与输出",
    "samplerAnisotropy": "画面与输出",
    "samplerLodBias": "画面与输出",
    "clampNegativeLodBias": "画面与输出",
    "numCompilerThreads": "性能优化",
    "enableGraphicsPipelineLibrary": "性能优化",
    "enableMemoryDefrag": "性能优化",
    "relaxedBarriers": "性能优化",
    "relaxedGraphicsBarriers": "性能优化",
    "maxFeatureLevel": "兼容性",
    "deferSurfaceCreation": "兼容性",
    "deviceFilter": "兼容性",
    "hideNvidiaGpu": "兼容性",
    "hideAmdGpu": "兼容性",
    "hideIntelGpu": "兼容性",
    "forceAspectRatio": "兼容性",
    "forceRefreshRate": "兼容性",
    "hud": "显示与诊断",
    "enableDebugUtils": "显示与诊断",
    "dpiAware": "显示与诊断",
}


def purpose_of(key: str) -> str:
    return PURPOSE.get(key, "其他")


def tier_of(key: str, section: str = "") -> str:
    """Lowest mode in which an option is listed."""
    if section == "d3d8" or key in LEGACY_KEYS:
        return "full"
    if key in BASIC_KEYS:
        return "simple"
    return "advanced"

# Keys that mean the same thing in different sections and should collapse into
# a single control that writes both lines.
KEY_ALIASES: tuple[tuple[str, ...], ...] = (
    ("syncInterval", "presentInterval"),
    ("maxFrameRate", "maxFrameRate"),
    ("maxFrameLatency", "maxFrameLatency"),
    ("enableHDR", "hdr"),
)


_OVERRIDES: dict[str, str] | None = None


def documentation_overrides() -> dict[str, str]:
    """Chinese documentation, keyed by option name.

    DXVK documents every option in English inside its own dxvk.conf; this file
    carries a translation so the interface stays in one language. The English
    original is still shown in the tooltip.
    """
    global _OVERRIDES
    if _OVERRIDES is None:
        _OVERRIDES = {}
        if str(settings.get("docs_language") or "zh") == "zh":
            path = asset_path("dxvk.conf.zh.json")
            try:
                if path.is_file():
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        _OVERRIDES = {str(k): str(v) for k, v in loaded.items()}
            except (OSError, ValueError):
                _OVERRIDES = {}
    # The fork's extra options are not in upstream's conf, so their text comes
    # from GPLASYNC_ONLY rather than from the bundled file.
    for key, item in GPLASYNC_ONLY.items():
        _OVERRIDES.setdefault(key, item["summary"])
    return _OVERRIDES


_LABELS: dict[str, str] | None = None


def _fork_labels() -> dict[str, str]:
    return {key: item["label"] for key, item in GPLASYNC_ONLY.items()}


def label_overrides() -> dict[str, str]:
    """Chinese option names, keyed by option name."""
    global _LABELS
    if _LABELS is None:
        _LABELS = {}
        if str(settings.get("docs_language") or "zh") == "zh":
            path = asset_path("dxvk.conf.zh.json")
            try:
                if path.is_file():
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    labels = loaded.get("_labels") if isinstance(loaded, dict) else None
                    if isinstance(labels, dict):
                        _LABELS = {str(k): str(v) for k, v in labels.items()}
            except (OSError, ValueError):
                _LABELS = {}
    for key, item in GPLASYNC_ONLY.items():
        _LABELS.setdefault(key, item["label"])
    return _LABELS


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

    def tooltip(self) -> str:
        """Full documentation for a hover tooltip: Chinese, example, English."""
        parts: list[str] = []
        translated = documentation_overrides().get(self.key, "")
        if translated:
            parts.append(translated)
        example = " | ".join(
            f"{member.qualified} = {member.example or _default_example(self.type)}"
            for member in self.members
        )
        parts.append(f"示例：{example}")
        original = self.description_en()
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


def _has_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


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


_FORK_CONF = """
[dxvk]
# GPLAsync 专有选项（官方 dxvk.conf 中不存在）
# dxvk.enableAsync = True
# dxvk.gplAsyncCache = True
"""


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


# --------------------------------------------------------------------------
# Where the reference comes from
# --------------------------------------------------------------------------

def newest_downloaded_reference() -> Path | None:
    """dxvk.conf from the newest downloaded DXVK package, if any."""
    for version in list_installed("dxvk"):
        found = reference_conf("dxvk", version)
        if found is not None:
            return found
    return None


def default_reference() -> tuple[Path | None, str]:
    """Resolve the reference file: explicit setting, bundled copy, release."""
    configured = str(settings.get("reference_conf") or "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_file():
            return candidate, "custom file"
    bundled = asset_path("dxvk.conf")
    if bundled.is_file():
        return bundled, "bundled reference"
    downloaded = newest_downloaded_reference()
    if downloaded is not None:
        return downloaded, "newest downloaded release"
    return None, ""


def load_model(path: Path | None = None) -> ConfModel:
    """Load the option catalogue from a file (or the default reference)."""
    if path is None:
        path, label = default_reference()
        if path is None:
            return build_model("", source="no reference file")
    else:
        label = "custom file"
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return build_model("", source=f"unreadable reference: {exc}")
    return build_model(text, source=label or str(path), path=Path(path))
