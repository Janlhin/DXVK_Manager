"""Per-target config storage and presets, without Qt.

The bridge owns the QML surface; this module owns the shapes written to
``settings.json``. Keeping them here makes the rules testable without a
QObject and keeps the bridge from growing another responsibility.

Every function takes an optional ``settings`` object with the same shape as
``dxvk_toolkit.paths.settings`` (get/set). The full application passes its
own; the standalone configurator passes its own, so the two tools keep their
presets apart instead of overwriting each other's keys.
"""

from __future__ import annotations

from typing import Any


def _app_settings() -> Any:
    """The full application's settings, imported lazily.

    Lazy on purpose: importing ``dxvk_toolkit.paths`` creates the data
    directory and reads the app's settings.json. The standalone configurator
    must not touch either - it keeps its own store - so the import only
    happens when a caller really wants the application defaults.
    """
    from ..paths import settings  # noqa: PLC0415

    return settings


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


def load_target_values(target: str, settings: Any = None) -> dict[str, Any]:
    store = settings or _app_settings()
    data = store.get(store_key(target))
    return dict(data) if isinstance(data, dict) else {}


def persist_target_values(target: str, values: dict[str, Any],
                          settings: Any = None) -> None:
    store = settings or _app_settings()
    store.set(store_key(target), dict(values))


def custom_presets(settings: Any = None) -> dict[str, Any]:
    store = settings or _app_settings()
    data = store.get("config_presets", {})
    return dict(data) if isinstance(data, dict) else {}


def preset_values(name: str, settings: Any = None) -> dict[str, Any]:
    """Selections a preset stands for; {} when the name is unknown."""
    if name in BUILTIN_PRESETS:
        return dict(BUILTIN_PRESETS[name])
    entry = custom_presets(settings).get(name)
    return dict(entry) if isinstance(entry, dict) else {}


def preset_names(settings: Any = None) -> list[str]:
    """Built-ins first, then the user's own presets in insertion order."""
    names = [*BUILTIN_PRESETS, PURE_PRESET]
    names.extend(key for key in custom_presets(settings) if key not in names)
    return names


def save_preset(name: str, values: dict[str, Any], settings: Any = None) -> bool:
    """Store a custom preset; False when the name belongs to a built-in."""
    store = settings or _app_settings()
    if not name or is_builtin(name):
        return False
    custom = custom_presets(store)
    custom[name] = dict(values)
    store.set("config_presets", custom)
    return True


def delete_preset(name: str, settings: Any = None) -> bool:
    """Remove a custom preset; False when it does not exist."""
    store = settings or _app_settings()
    custom = custom_presets(store)
    if name not in custom:
        return False
    del custom[name]
    store.set("config_presets", custom)
    return True
