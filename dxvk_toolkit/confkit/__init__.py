"""A small, application-independent toolkit for dxvk.conf files.

Nothing here imports the application: the language and the asset directory are
supplied through :func:`configure`, so this package can be copied elsewhere and
used on its own.

Layering (each module only imports the ones above it):
    base    parsing helpers
    curate  which options count as basic / advanced / legacy
    i18n    documentation and labels
    model   the option model
    parse   reference conf  <->  option model
    build   selection  ->  dxvk.conf text
"""

from __future__ import annotations

from .base import (
    BOOLEAN_RE,
    COMMENT_RE,
    KEY_RE,
    NUMBER_RE,
    SECTION_RE,
    _clean_value,
    _default_example,
    _has_value,
    _infer_type,
    _pretty_label,
)
from .build import (
    HEADER,
    build_conf,
    count_lines,
    format_value,
    selection_summary,
)
from .curate import (
    BASIC_KEYS,
    GPLASYNC_ONLY,
    LEGACY_KEYS,
    MODES,
    PURPOSE,
    PURPOSE_ORDER,
    build_of,
    purpose_of,
    tier_of,
)
from .i18n import configure, documentation_overrides, label_overrides
from .model import ConfModel, Member, OptionGroup
from .parse import build_model, consolidate, parse_conf_text, parse_config_values

__all__ = [
    "BASIC_KEYS", "BOOLEAN_RE", "COMMENT_RE", "ConfModel", "GPLASYNC_ONLY", "HEADER",
    "KEY_RE", "LEGACY_KEYS", "MODES", "Member", "NUMBER_RE", "OptionGroup", "PURPOSE",
    "PURPOSE_ORDER", "SECTION_RE", "build_conf", "build_model", "build_of", "configure",
    "consolidate", "count_lines", "documentation_overrides", "format_value",
    "label_overrides", "parse_config_values", "parse_conf_text", "purpose_of",
    "selection_summary", "tier_of",
]
