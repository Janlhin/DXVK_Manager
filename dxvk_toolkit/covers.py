"""Game cover art: resolve a source URL, cache it, and slice the variants.

Covers are cosmetic, so every failure path degrades to "no artwork" instead of
raising. Pillow decodes JPEG and bakes the rounded card / circular avatar
variants the QML interface loads; without Pillow the original cover is still
served and the cards simply show their platform colour.
"""

# pyright: reportOptionalMemberAccess=warning
# Pillow is an optional, untyped dependency; its members are only touched under
# the HAS_PIL runtime guard, so the static "None" narrowing below is a false
# positive, not a real null-deref bug.

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import net
from .paths import covers_dir
from .util import log

# Pillow is optional: artwork is nice, not essential. It is imported alone so
# a tkinter-less interpreter keeps working - the retired Tk front end was the
# only consumer of ImageTk, and requiring it used to disable every cover
# operation (including the QML slicing) when tkinter was absent.
try:
    from PIL import Image, ImageDraw

    HAS_PIL = True
except Exception:  # noqa: BLE001 - any import problem disables artwork
    Image = ImageDraw = None  # type: ignore[assignment]
    HAS_PIL = False

# Portrait card artwork, the shape store fronts use.
CARD_SIZE = (168, 252)
# Only the top two corners are rounded: the bottom meets the card footer, so
# rounding it would expose the card background. (§22 cover rounding, scheme B.)
CARD_RADIUS = 6
# List avatar: a full circle. (§22 cover rounding, scheme B.)
ROUND_SIZE = (36, 36)
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
    """Pre-sliced card cover: portrait, top corners rounded (§22 scheme B)."""
    return covers_dir() / f"{safe_key(key)}_card.png"


def round_path(key: str) -> Path:
    """Pre-sliced list avatar: a full circle (§22 scheme B)."""
    return covers_dir() / f"{safe_key(key)}_round.png"


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


_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF8")


def _is_image(path: Path) -> bool:
    """A cover must actually be an image.

    A missing asset host answers with an HTML error page; saving that as .jpg
    produced "Error decoding" spam and a broken card.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    return any(head.startswith(magic) for magic in _IMAGE_MAGIC)


def download_cover(key: str, urls: Sequence[str], timeout: float = 25.0) -> bool:
    """Fetch the first working URL into the cache. Returns True on success."""
    if not urls:
        return False
    target = original_path(key)
    if target.is_file() and target.stat().st_size > 1024 and _is_image(target):
        return True
    for url in urls:
        try:
            net.http_download(url, target, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - artwork is optional
            log.debug("cover download failed (%s): %s", url, exc)
            continue
        if target.is_file() and target.stat().st_size > 1024 and _is_image(target):
            return True
        # Not an image: drop it so the next run retries a different host.
        if target.is_file() and not _is_image(target):
            log.debug("cover at %s is not an image, discarding", url)
            try:
                target.unlink()
            except OSError:
                pass
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


def _rounded_top_mask(size: tuple[int, int], radius: int) -> Any:
    """Alpha mask: top corners rounded by `radius`, bottom corners square.

    The bottom of a card cover sits against the card footer, so only the
    top two corners are clipped (§22 cover rounding, scheme B). Three fills
    build the shape: everything below the corner arcs, the strip between
    the two arcs (missing this made the whole top edge transparent - the
    platform colour showed through as a "blue border"), and the arcs.
    """
    width, height = size
    radius = min(radius, width // 2, height // 2)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, radius, width - 1, height - 1], fill=255)
    draw.rectangle([radius, 0, width - 1 - radius, radius - 1], fill=255)
    draw.pieslice([0, 0, 2 * radius, 2 * radius], 180, 270, fill=255)
    draw.pieslice([width - 2 * radius, 0, width - 1, 2 * radius], 270, 360, fill=255)
    return mask


def _circle_mask(size: tuple[int, int]) -> Any:
    width, height = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, width - 1, height - 1], fill=255)
    return mask


def _apply_alpha(image: Any, mask: Any) -> Any:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    image.putalpha(mask)
    return image


def ensure_card(key: str, size: tuple[int, int] = CARD_SIZE, radius: int = CARD_RADIUS) -> Path | None:
    """Create the pre-sliced, top-rounded PNG used by the card grid (Pillow).

    The rounded corners are baked into the cached file (§22 scheme B), so the
    Qt UI just loads this PNG and needs no shader mask. (§22)
    """
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
            card = _apply_alpha(card, _rounded_top_mask(size, radius))
            target.parent.mkdir(parents=True, exist_ok=True)
            card.save(target, "PNG", optimize=True)
        return target
    except Exception as exc:  # noqa: BLE001 - a broken image must not break the grid
        log.debug("cover resize failed for %s: %s", key, exc)
        return None


def ensure_round(key: str, size: tuple[int, int] = ROUND_SIZE) -> Path | None:
    """Create the pre-sliced circular PNG used by the list avatar (Pillow).

    Baked as a transparent circle so the Qt row just loads it over the
    platform-coloured disc (§22 scheme B). (§22)
    """
    if not HAS_PIL:
        return None
    source = original_path(key)
    if not source.is_file():
        return None
    target = round_path(key)
    try:
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        with Image.open(source) as image:
            thumb = _fit(image.convert("RGB"), size)
            thumb = _apply_alpha(thumb, _circle_mask(size))
            target.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(target, "PNG", optimize=True)
        return target
    except Exception as exc:  # noqa: BLE001 - a broken image must not break the list
        log.debug("cover round failed for %s: %s", key, exc)
        return None
