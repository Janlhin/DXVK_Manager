"""App-side view of the config layer.

The portable half now lives in :mod:`dxvk_toolkit.confkit` and knows nothing
about this application. What stays here is what does: where the reference
dxvk.conf comes from (the `reference_conf` setting, or the newest downloaded
package) and which language the interface is running in.

Existing call sites keep importing this module, so the split changed no API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import confkit
from .confkit import (  # re-exported for existing call sites
    BASIC_KEYS,
    BOOLEAN_RE,
    COMMENT_RE,
    GPLASYNC_ONLY,
    KEY_RE,
    LEGACY_KEYS,
    MODES,
    NUMBER_RE,
    PURPOSE,
    PURPOSE_ORDER,
    SECTION_RE,
    ConfModel,
    Member,
    OptionGroup,
    build_model,
    build_of,
    consolidate,
    parse_conf_text,
    parse_config_values,
    purpose_of,
    tier_of,
)
from .confkit.validate import ValidationError, MAX_CONF_BYTES
from .paths import asset_path, settings
from .sources import list_installed, reference_conf


def _configure() -> None:
    """Point confkit at this application's language and asset folder."""
    confkit.configure(
        lang=str(settings.get("docs_language") or "zh"),
        assets_dir=asset_path("dxvk.conf.zh.json").parent,
    )


def documentation_overrides() -> dict[str, str]:
    """Chinese documentation for the language the interface is set to."""
    _configure()
    return confkit.documentation_overrides()


def label_overrides() -> dict[str, str]:
    """Chinese option names for the language the interface is set to."""
    _configure()
    return confkit.label_overrides()


_configure()


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
        if Path(path).stat().st_size > MAX_CONF_BYTES:
            raise ValidationError(
                f"reference file too large: {Path(path).stat().st_size} bytes "
                f"exceeds limit of {MAX_CONF_BYTES}"
            )
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return build_model("", source=f"unreadable reference: {exc}")
    return build_model(text, source=label or str(path), path=Path(path))
