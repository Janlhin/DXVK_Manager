"""Chinese documentation and labels for the option catalogue.

The host supplies the language and the asset directory, and this module never
reads application settings - that is what keeps the package portable.
"""

from __future__ import annotations

import json
from pathlib import Path

from .curate import GPLASYNC_ONLY

_FILENAME = "dxvk.conf.zh.json"
_lang = "zh"
_assets: Path | None = None
_cache: dict[str, tuple[dict[str, str], dict[str, str]]] = {}


def configure(*, lang: str | None = None, assets_dir: str | Path | None = None) -> None:
    """Tell the package which language to use and where its assets live."""
    global _lang, _assets
    if lang is not None and lang != _lang:
        _lang = lang
        _cache.clear()
    if assets_dir is not None:
        folder = Path(assets_dir)
        if folder != _assets:
            _assets = folder
            _cache.clear()


def _load(lang: str) -> tuple[dict[str, str], dict[str, str]]:
    cached = _cache.get(lang)
    if cached is not None:
        return cached

    docs: dict[str, str] = {}
    labels: dict[str, str] = {}
    if lang == "zh" and _assets is not None:
        path = _assets / _FILENAME
        try:
            if path.is_file():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw_labels = loaded.get("_labels")
                    if isinstance(raw_labels, dict):
                        labels = {str(k): str(v) for k, v in raw_labels.items()}
                    docs = {
                        str(k): str(v)
                        for k, v in loaded.items()
                        if not str(k).startswith("_")
                    }
        except (OSError, ValueError):
            docs, labels = {}, {}

    # The fork's extra options are absent from upstream's conf, so their text
    # ships with the code rather than with the reference file.
    for key, item in GPLASYNC_ONLY.items():
        docs.setdefault(key, item["summary"])
        labels.setdefault(key, item["label"])

    _cache[lang] = (docs, labels)
    return docs, labels


def documentation_overrides(lang: str | None = None) -> dict[str, str]:
    """Chinese documentation, keyed by option name."""
    return _load(lang or _lang)[0]


def label_overrides(lang: str | None = None) -> dict[str, str]:
    """Chinese option names, keyed by option name."""
    return _load(lang or _lang)[1]
