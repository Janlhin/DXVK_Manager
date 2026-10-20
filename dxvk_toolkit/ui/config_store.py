"""Per-target config storage and presets, without Qt.

The bridge owns the QML surface; this module owns the shapes written to
``settings.json``. Keeping them here makes the rules testable without a
QObject and keeps the bridge from growing another responsibility.
"""

from __future__ import annotations

from typing import Any

from ..paths import settings

# Option key -> True/False (booleans) or a value string. Keys are the bare
# option names from the catalogue (no dxvk./dxgi. prefix); keys the loaded
# reference does not know are skipped on apply.
BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "性能优先": {
        "tearFree": False,
        "syncInterval": "0",
        "relaxedGraphicsBarriers": True,
        "relaxedBarriers": True,
        "enableGraphicsPipelineLibrary": True,
    },
    "兼容优先": {
        "useRawSsbo": True,
        "seamlessCubes": True,
        "lenientClear": True,
        "clampNegativeLodBias": True,
        "deferSurfaceCreation": True,
        "enableUe4Workarounds": True,
    },
}

# "Apply nothing" is expressed as a preset name in the UI, not a stored table.
PURE_PRESET = "纯净"


def is_builtin(name: str) -> bool:
    """True for the names the user must not overwrite."""
    return name in BUILTIN_PRESETS or name == PURE_PRESET


def store_key(target: str) -> str:
    """Settings key holding one target's selections ("" = shared default)."""
    return "config_default" if not target else f"config_game:{target}"


def load_target_values(target: str) -> dict[str, Any]:
    data = settings.get(store_key(target))
    return dict(data) if isinstance(data, dict) else {}


def persist_target_values(target: str, values: dict[str, Any]) -> None:
    settings.set(store_key(target), dict(values))


def custom_presets() -> dict[str, Any]:
    data = settings.get("config_presets", {})
    return dict(data) if isinstance(data, dict) else {}


def preset_values(name: str) -> dict[str, Any]:
    """Selections a preset stands for; {} when the name is unknown."""
    if name in BUILTIN_PRESETS:
        return dict(BUILTIN_PRESETS[name])
    entry = custom_presets().get(name)
    return dict(entry) if isinstance(entry, dict) else {}


def preset_names() -> list[str]:
    """Built-ins first, then the user's own presets in insertion order."""
    names = [*BUILTIN_PRESETS, PURE_PRESET]
    names.extend(key for key in custom_presets() if key not in names)
    return names


def save_preset(name: str, values: dict[str, Any]) -> bool:
    """Store a custom preset; False when the name belongs to a built-in."""
    if not name or is_builtin(name):
        return False
    custom = custom_presets()
    custom[name] = dict(values)
    settings.set("config_presets", custom)
    return True


def delete_preset(name: str) -> bool:
    """Remove a custom preset; False when it does not exist."""
    custom = custom_presets()
    if name not in custom:
        return False
    del custom[name]
    settings.set("config_presets", custom)
    return True
