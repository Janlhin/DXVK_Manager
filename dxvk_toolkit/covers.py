"""Game cover art: resolve a source URL, cache it, hand Tk a ready image.

Covers are cosmetic, so every failure path degrades to a locally drawn
placeholder instead of raising. Pillow is used when present (it decodes JPEG,
which Tk cannot); without it the grid still works, just without artwork.
"""

from __future__ import annotations

import hashlib
import os
import queue
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from . import net
from .paths import covers_dir
from .util import log

try:  # Pillow is optional: artwork is nice, not essential.
    from PIL import Image, ImageDraw, ImageTk

    HAS_PIL = True
except Exception:  # noqa: BLE001 - any import problem disables artwork
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]
    HAS_PIL = False

# Portrait card artwork, the shape store fronts use.
CARD_SIZE = (168, 252)
# The Cloudflare host is canonical but is frequently slow or unreachable in
# some regions, so every asset is tried on each host in turn.
STEAM_CDN_HOSTS = (
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{name}",
    "https://shared.fastly.steamstatic.com/steam/apps/{appid}/{name}",
    "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/{name}",
    "https://steamcdn-a.akamaihd.net/steam/apps/{appid}/{name}",
)

# Tried in order; the portrait library asset looks best in a card grid.
STEAM_ASSETS = ("library_600x900.jpg", "library_600x900_2x.jpg", "header.jpg", "capsule_231x87.jpg")

PLATFORM_COLORS = {
    "steam": "#1b6ab8",
    "epic": "#2a2a2a",
    "gog": "#7b3fa0",
    "ubisoft": "#0a63b0",
    "battlenet": "#0f6fbf",
    "riot": "#c0392b",
    "wegame": "#c0392b",
    "mihoyo": "#3c6ea5",
    "ea": "#c0392b",
    "manual": "#4a5568",
    "unknown": "#3a4150",
}

_PHOTO_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_PHOTO_LIMIT = 90


def platform_color(platform: str) -> str:
    return PLATFORM_COLORS.get((platform or "").lower(), PLATFORM_COLORS["unknown"])


def cover_key(game: Any) -> str:
    """Stable cache key for a game (survives reinstalls and path changes)."""
    platform = str(getattr(game, "source", "manual") or "manual")
    appid = str(getattr(game, "appid", "") or "")
    if platform == "steam" and appid.isdigit():
        return f"steam-{appid}"
    if appid and appid not in ("manual", "0"):
        return f"{platform}-{appid}"
    install_dir = str(getattr(game, "install_dir", ""))
    digest = hashlib.sha1(os.path.normcase(install_dir).encode("utf-8", "replace")).hexdigest()[:16]
    return f"{platform}-{digest}"


_UNSAFE_KEY = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_key(key: str) -> str:
    """Make a cache key safe to use as a single file name.

    Callers have handed this function absolute install paths by mistake; on
    Windows Path(root) / "d:\\game" silently becomes "d:\\game", which wrote
    cover files next to the games. Strip everything that could escape.
    """
    cleaned = _UNSAFE_KEY.sub("_", str(key or "")).strip(" .")
    return cleaned[:120] or "unknown"


def original_path(key: str) -> Path:
    return covers_dir() / f"{safe_key(key)}.jpg"


def card_path(key: str) -> Path:
    size = f"{CARD_SIZE[0]}x{CARD_SIZE[1]}"
    return covers_dir() / f"{safe_key(key)}_{size}.png"


def source_urls(game: Any) -> list[str]:
    """Candidate cover URLs, best first."""
    platform = str(getattr(game, "source", "manual") or "manual")
    appid = str(getattr(game, "appid", "") or "")
    urls: list[str] = []
    if platform == "steam" and appid.isdigit():
        for asset in STEAM_ASSETS:
            urls.extend(host.format(appid=appid, name=asset) for host in STEAM_CDN_HOSTS)
    explicit = str(getattr(game, "cover_url", "") or "")
    if explicit:
        urls.insert(0, explicit)
    return urls


def download_cover(key: str, urls: Sequence[str], timeout: float = 25.0) -> bool:
    """Fetch the first working URL into the cache. Returns True on success."""
    if not urls:
        return False
    target = original_path(key)
    if target.is_file() and target.stat().st_size > 1024:
        return True
    for url in urls:
        try:
            net.http_download(url, target, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - artwork is optional
            log.debug("cover download failed (%s): %s", url, exc)
            continue
        if target.is_file() and target.stat().st_size > 1024:
            return True
    return False


def _fit(image: Any, size: tuple[int, int]) -> Any:
    """Center-crop to the card aspect ratio, then resize."""
    target_w, target_h = size
    target_ratio = target_w / target_h
    width, height = image.size
    ratio = width / height if height else target_ratio
    if ratio > target_ratio:
        new_w = int(height * target_ratio)
        left = (width - new_w) // 2
        image = image.crop((left, 0, left + new_w, height))
    elif ratio < target_ratio:
        new_h = int(width / target_ratio)
        top = (height - new_h) // 2
        image = image.crop((0, top, width, top + new_h))
    resample = getattr(Image, "LANCZOS", None) or getattr(Image, "BICUBIC", 1)
    return image.resize((target_w, target_h), resample)


def ensure_card(key: str, size: tuple[int, int] = CARD_SIZE) -> Path | None:
    """Create the pre-scaled PNG used by the grid (requires Pillow)."""
    if not HAS_PIL:
        return None
    source = original_path(key)
    if not source.is_file():
        return None
    target = card_path(key)
    try:
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        with Image.open(source) as image:
            card = _fit(image.convert("RGB"), size)
            target.parent.mkdir(parents=True, exist_ok=True)
            card.save(target, "PNG", optimize=True)
        return target
    except Exception as exc:  # noqa: BLE001 - a broken image must not break the grid
        log.debug("cover resize failed for %s: %s", key, exc)
        return None


def placeholder_image(label: str, size: tuple[int, int] = CARD_SIZE, color: str = "") -> Any:
    """A drawn cover stand-in: platform colour plus the game initials."""
    if not HAS_PIL:
        return None
    base = color or PLATFORM_COLORS["unknown"]
    image = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(image)
    width, height = size
    # Simple diagonal sheen so the placeholder does not look broken.
    for offset in range(0, height, 6):
        shade = 8 + int(24 * offset / max(1, height))
        draw.line([(0, offset), (width, offset - width // 3)], fill=_shade(base, shade), width=6)
    initials = "".join(word[0] for word in str(label).split()[:3]).upper() or "?"
    font = None
    try:
        from PIL import ImageFont

        for candidate in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(candidate, int(height * 0.22))
                break
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        font = None
    text_w, text_h = draw.textbbox((0, 0), initials, font=font)[2:] if font else (0, 0)
    draw.text(
        ((width - text_w) / 2, (height - text_h) / 2 - height * 0.05),
        initials,
        fill="#e7e9ec",
        font=font,
    )
    return image


def _shade(color: str, amount: int) -> tuple[int, int, int]:
    color = color.lstrip("#")
    try:
        r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        r, g, b = 60, 65, 80
    return (min(255, r + amount), min(255, g + amount), min(255, b + amount))


_PLACEHOLDER_CACHE: dict[str, Any] = {}


def platform_placeholder(platform: str, size: tuple[int, int] = CARD_SIZE) -> Any:
    """A neutral card image for one platform, drawn once and reused.

    Game initials are drawn on top by the grid as canvas text, which keeps
    placeholder cost independent of how many games are on screen.
    """
    if not HAS_PIL:
        return None
    key = f"{platform or 'unknown'}:{size[0]}x{size[1]}"
    cached = _PLACEHOLDER_CACHE.get(key)
    if cached is not None:
        return cached
    image = placeholder_image(platform or "?", size, platform_color(platform))
    if image is None:
        return None
    try:
        photo = ImageTk.PhotoImage(image)
    except Exception as exc:  # noqa: BLE001
        log.debug("placeholder creation failed: %s", exc)
        return None
    _PLACEHOLDER_CACHE[key] = photo
    return photo


def photo_for(
    key: str,
    *,
    label: str = "",
    color: str = "",
    size: tuple[int, int] = CARD_SIZE,
) -> Any:
    """A Tk-ready image for a card, from cache when possible.

    Returns None when Pillow is unavailable, in which case the caller draws
    its own placeholder on a canvas.
    """
    if not HAS_PIL:
        return None
    cache_key = f"{key}:{size[0]}x{size[1]}"
    cached = _PHOTO_CACHE.get(cache_key)
    if cached is not None:
        _PHOTO_CACHE.move_to_end(cache_key)
        return cached

    image = None
    path = card_path(key)
    if path.is_file():
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            log.debug("cover load failed for %s: %s", key, exc)
    if image is None:
        image = placeholder_image(label or key, size, color)
    if image is None:
        return None
    try:
        photo = ImageTk.PhotoImage(image)
    except Exception as exc:  # noqa: BLE001 - no display / no Tk support
        log.debug("PhotoImage creation failed: %s", exc)
        return None
    _PHOTO_CACHE[cache_key] = photo
    while len(_PHOTO_CACHE) > _PHOTO_LIMIT:
        _PHOTO_CACHE.popitem(last=False)
    return photo


def forget(key: str) -> None:
    for cache_key in [k for k in _PHOTO_CACHE if k.startswith(f"{key}:")]:
        _PHOTO_CACHE.pop(cache_key, None)


class CoverLoader:
    """Background cover downloader that hands results back on the Tk thread.

    The grid only asks for the cards that are actually visible, so opening a
    library of a hundred games costs a handful of requests, not a hundred.
    """

    def __init__(self, root: Any, *, workers: int = 4, interval_ms: int = 70) -> None:
        self._root = root
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cover")
        self._queue: "queue.Queue[tuple[str, list[str], Callable[[str, bool], None]]]" = queue.Queue()
        self._results: "queue.Queue[tuple[str, bool, Callable[[str, bool], None]]]" = queue.Queue()
        self._pending: set[str] = set()
        self._stopped = False
        self._timer: str | None = None
        for _ in range(workers):
            self._pool.submit(self._worker)
        self._timer = self._root.after(interval_ms, self._drain)

    # -- public API ------------------------------------------------------
    def request(self, key: str, urls: Iterable[str], callback: Callable[[str, bool], None]) -> None:
        """Ask for a cover; callback(key, ok) runs on the Tk thread."""
        if self._stopped or key in self._pending:
            return
        url_list = [url for url in urls if url]
        cached = card_path(key).is_file() or original_path(key).is_file()
        if cached:
            # Already on disk: only the resize step is needed.
            self._pending.add(key)
            self._pool.submit(self._finish_cached, key, callback)
            return
        if not url_list:
            return
        self._pending.add(key)
        self._queue.put((key, url_list, callback))

    def pending(self, key: str) -> bool:
        return key in self._pending

    def shutdown(self) -> None:
        self._stopped = True
        if self._timer is not None:
            try:
                self._root.after_cancel(self._timer)
            except Exception:  # noqa: BLE001
                pass
            self._timer = None
        self._pool.shutdown(wait=False, cancel_futures=True)

    # -- internals -------------------------------------------------------
    def _worker(self) -> None:
        while not self._stopped:
            try:
                key, urls, callback = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                ok = download_cover(key, urls)
                if ok:
                    ok = ensure_card(key) is not None
            except Exception as exc:  # noqa: BLE001
                log.debug("cover worker failed for %s: %s", key, exc)
                ok = False
            self._results.put((key, ok, callback))

    def _finish_cached(self, key: str, callback: Callable[[str, bool], None]) -> None:
        try:
            ok = ensure_card(key) is not None
        except Exception:  # noqa: BLE001
            ok = False
        self._results.put((key, ok, callback))

    def _drain(self) -> None:
        self._timer = None
        if self._stopped:
            return
        delivered = 0
        while delivered < 12:
            try:
                key, ok, callback = self._results.get_nowait()
            except queue.Empty:
                break
            self._pending.discard(key)
            try:
                callback(key, ok)
            except Exception as exc:  # noqa: BLE001
                log.debug("cover callback failed: %s", exc)
            delivered += 1
        if self._stopped:
            return
        try:
            self._timer = self._root.after(70, self._drain)
        except Exception:  # noqa: BLE001 - window closed
            self._stopped = True
