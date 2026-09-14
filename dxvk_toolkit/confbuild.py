"""App-side alias for :mod:`dxvk_toolkit.confkit.build`.

The implementation moved into the confkit package (which knows nothing about
this application). This module stays so existing call sites and tests keep
importing the same names.
"""

from __future__ import annotations

from .confkit.build import (
    COMMENT_WIDTH,
    HEADER,
    build_conf,
    comment_block,
    count_lines,
    format_value,
    selection_summary,
    wrap_comment,
)

__all__ = [
    "COMMENT_WIDTH",
    "HEADER",
    "build_conf",
    "comment_block",
    "count_lines",
    "format_value",
    "selection_summary",
    "wrap_comment",
]
