"""Optional PCGamingWiki enrichment with an on-disk cache.

Everything here is best effort: the application must stay fully usable with no
network at all, so every function returns cached or empty data instead of
raising.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import net
from .paths import covers_dir, meta_dir
from .util import log

PCGW_QUERY = (
    "https://www.pcgamingwiki.com/w/api.php?action=cargoquery"
    "&tables=Infobox_game,API"
    "&fields=Infobox_game._pageName=Page,Infobox_game.Cover_URL=Cover,"
    "API.Direct3D_versions=Direct3D,API.Vulkan_versions=Vulkan,"
    "API.Windows_32bit_executable=Win32,API.Windows_64bit_executable=Win64"
    "&join_on=Infobox_game._pageID=API._pageID"
    '&where=Infobox_game.Steam_AppID%20HOLDS%20%22{appid}%22&format=json&limit=1'
)

CACHE_DAYS = 45


def _cache_file(appid: str) -> Path:
    return meta_dir() / f"{appid}.json"


def load_cached(appid: str) -> dict[str, Any] | None:
    path = _cache_file(appid)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def save_cached(appid: str, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["fetched_at"] = time.time()
    try:
        _cache_file(appid).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        log.debug("could not cache metadata for %s: %s", appid, exc)


def is_stale(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return True
    fetched = float(payload.get("fetched_at") or 0)
    return (time.time() - fetched) > CACHE_DAYS * 86400


def _first_row(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        rows = payload.get("cargoquery")
        if isinstance(rows, list) and rows:
            first = rows[0]
            if isinstance(first, dict):
                title = first.get("title")
                if isinstance(title, dict):
                    return title
                return first
    return {}


def fetch(appid: str, *, timeout: float = 25.0) -> dict[str, Any]:
    """Look a Steam app up on PCGamingWiki; returns {} when unavailable."""
    if not appid or not appid.isdigit():
        return {}
    try:
        payload = net.get_json(PCGW_QUERY.format(appid=appid), timeout=timeout, retries=2)
    except (net.NetworkError, ValueError) as exc:
        log.info("PCGamingWiki lookup failed for %s: %s", appid, exc)
        return {}
    row = _first_row(payload)
    if not row:
        return {}
    result = {
        "page": str(row.get("Page") or ""),
        "cover_url": str(row.get("Cover") or ""),
        "direct3d": str(row.get("Direct3D") or ""),
        "vulkan": str(row.get("Vulkan") or ""),
        "win32": str(row.get("Win32") or ""),
        "win64": str(row.get("Win64") or ""),
    }
    save_cached(appid, result)
    return result


def get(appid: str, *, allow_network: bool = True) -> dict[str, Any]:
    """Cached metadata, refreshed when stale and the network allows it."""
    cached = load_cached(appid)
    if cached and not is_stale(cached):
        return cached
    if not allow_network:
        return cached or {}
    fresh = fetch(appid)
    if fresh:
        return fresh
    return cached or {}


def cover_path(appid: str) -> Path:
    return covers_dir() / f"{appid}.jpg"


def ensure_cover(appid: str, url: str) -> Path | None:
    """Download the cover once; returns the local path when available."""
    target = cover_path(appid)
    if target.is_file() and target.stat().st_size > 0:
        return target
    if not url:
        return None
    try:
        net.http_download(url, target, timeout=30)
    except Exception as exc:  # noqa: BLE001 - covers are cosmetic
        log.debug("cover download failed for %s: %s", appid, exc)
        return None
    return target if target.is_file() and target.stat().st_size > 0 else None
