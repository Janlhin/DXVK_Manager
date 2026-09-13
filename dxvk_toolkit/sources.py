"""DXVK and DXVK-gplasync release discovery, download and extraction."""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from . import net
from .paths import archives_dir, cache_dir, data_root, settings
from .util import log, parse_version_tuple, safe_name

GITHUB_RELEASES = "https://api.github.com/repos/doitsujin/dxvk/releases?per_page=100&page={page}"
GITLAB_TREE = (
    "https://gitlab.com/api/v4/projects/Ph42oN%2Fdxvk-gplasync/repository/tree"
    "?path=releases&ref=main&per_page=100&page={page}"
)
GITLAB_RAW = "https://gitlab.com/Ph42oN/dxvk-gplasync/-/raw/main/releases/{name}"
ATOM_FEED = "https://github.com/doitsujin/dxvk/releases.atom"
GITHUB_DOWNLOAD = "https://github.com/doitsujin/dxvk/releases/download/{tag}/{name}"
# jsDelivr's data API lists repository tags and is reachable where GitHub is
# not; it is the last listing fallback because tags are not releases.
JSDELIVR_TAGS = "https://data.jsdelivr.com/v1/packages/gh/doitsujin/dxvk"

# Prefixes that mirror github.com release downloads. They only ever carry the
# same public files, but they are third parties, so they are used only as a
# fallback and can be turned off entirely in the settings.
MIRROR_PREFIXES = (
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://gh.llkk.cc/",
)

ARCH_FOLDERS = ("x32", "x64")

ProgressFn = Callable[[int, int], None]


@dataclass
class Release:
    """One downloadable DXVK package."""

    kind: str  # "dxvk" or "gplasync"
    version: str
    label: str
    url: str
    date: str = ""
    size: int = 0
    file_name: str = ""

    @property
    def sort_key(self) -> tuple[int, ...]:
        return parse_version_tuple(self.version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version,
            "label": self.label,
            "url": self.url,
            "date": self.date,
            "size": self.size,
            "file_name": self.file_name,
        }


def _dxvk_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    tag = str(release.get("tag_name") or "")
    plain = tag.lstrip("v")
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        if "native" in name:
            continue
        if name == f"dxvk-{plain}.tar.gz":
            return asset
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        if name.endswith(".tar.gz") and "native" not in name:
            return asset
    return None


def download_candidates(url: str) -> list[str]:
    """URLs to try for a release asset, best first.

    "auto" (the default) tries the official host and then the mirrors, so a
    blocked or throttled GitHub still works. "official" never touches a mirror.
    """
    mode = str(settings.get("download_source") or "auto")
    if mode == "official" or not url.startswith("https://github.com/"):
        return [url]
    prefixes: list[str]
    if mode.startswith("mirror:"):
        prefixes = [mode.split(":", 1)[1].rstrip("/") + "/"]
    else:
        prefixes = list(MIRROR_PREFIXES)
    return [url] + [prefix + url for prefix in prefixes]


def _jsdelivr_releases() -> list[Release]:
    """Version list from jsDelivr tags (used when GitHub itself is blocked)."""
    payload = net.get_json(JSDELIVR_TAGS, timeout=30, retries=2)
    versions = payload.get("versions") if isinstance(payload, dict) else None
    releases: list[Release] = []
    for item in versions or []:
        tag = str(item.get("version") if isinstance(item, dict) else item or "").strip()
        if not tag:
            continue
        if not tag.startswith("v"):
            tag = "v" + tag
        file_name = f"dxvk-{tag.lstrip('v')}.tar.gz"
        releases.append(
            Release(
                kind="dxvk",
                version=tag,
                label=f"DXVK {tag}",
                url=GITHUB_DOWNLOAD.format(tag=tag, name=file_name),
                date="",
                size=0,
                file_name=file_name,
            )
        )
    releases.sort(key=lambda r: r.sort_key, reverse=True)
    return releases


def _cache_file(kind: str) -> Path:
    folder = data_root() / "releases"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{kind}.json"


def cache_releases(kind: str, releases: list[Release]) -> None:
    """Persist a listing so the app still works offline or while rate limited."""
    payload = {
        "fetched_at": time.time(),
        "releases": [release.to_dict() for release in releases],
    }
    try:
        _cache_file(kind).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log.debug("could not cache %s releases: %s", kind, exc)


def cached_releases(kind: str) -> list[Release]:
    try:
        payload = json.loads(_cache_file(kind).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = payload.get("releases") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    releases: list[Release] = []
    for item in items:
        if isinstance(item, dict) and item.get("version") and item.get("url"):
            releases.append(
                Release(
                    kind=str(item.get("kind") or kind),
                    version=str(item["version"]),
                    label=str(item.get("label") or item["version"]),
                    url=str(item["url"]),
                    date=str(item.get("date") or ""),
                    size=int(item.get("size") or 0),
                    file_name=str(item.get("file_name") or ""),
                )
            )
    releases.sort(key=lambda r: r.sort_key, reverse=True)
    return releases


def cache_age(kind: str) -> float:
    try:
        payload = json.loads(_cache_file(kind).read_text(encoding="utf-8"))
        return max(0.0, time.time() - float(payload.get("fetched_at") or 0))
    except (OSError, ValueError, TypeError):
        return float("inf")


def _atom_dxvk_releases() -> list[Release]:
    """Fallback listing that does not touch the (rate limited) GitHub API.

    github.com/doitsujin/dxvk/releases.atom is a plain feed, and release assets
    live at a predictable URL, so both the version list and the download link
    can be rebuilt without an API token.
    """
    body = net.http_get(ATOM_FEED, timeout=30, retries=2).decode("utf-8", "replace")
    releases: list[Release] = []
    for chunk in body.split("<entry>")[1:]:
        title_match = re.search(r"<title>([^<]*)</title>", chunk)
        link_match = re.search(r'href="([^"]*?/releases/tag/([^"]+))"', chunk)
        date_match = re.search(r"<updated>([^<]+)</updated>", chunk)
        if not link_match:
            continue
        tag = link_match.group(2).strip()
        if not tag:
            continue
        file_name = f"dxvk-{tag.lstrip('v')}.tar.gz"
        releases.append(
            Release(
                kind="dxvk",
                version=tag,
                label=(title_match.group(1).strip() if title_match else f"DXVK {tag}"),
                url=GITHUB_DOWNLOAD.format(tag=tag, name=file_name),
                date=(date_match.group(1)[:10] if date_match else ""),
                size=0,
                file_name=file_name,
            )
        )
    releases.sort(key=lambda r: r.sort_key, reverse=True)
    return releases


def fetch_dxvk_releases(pages: int = 2, *, allow_network: bool = True) -> list[Release]:
    """Upstream DXVK releases, newest first.

    Tries the GitHub API, falls back to the release feed when the API is
    unavailable or rate limited, and finally falls back to the last cached
    listing so the UI is never empty on a working machine.
    """
    if allow_network:
        try:
            releases: list[Release] = []
            for page in range(1, max(1, pages) + 1):
                payload = net.get_json(GITHUB_RELEASES.format(page=page))
                if not isinstance(payload, list) or not payload:
                    break
                for entry in payload:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("draft") or entry.get("prerelease"):
                        continue
                    asset = _dxvk_asset(entry)
                    if not asset:
                        continue
                    tag = str(entry.get("tag_name") or "")
                    releases.append(
                        Release(
                            kind="dxvk",
                            version=tag,
                            label=str(entry.get("name") or f"DXVK {tag}"),
                            url=str(asset.get("browser_download_url") or ""),
                            date=str(entry.get("published_at") or "")[:10],
                            size=int(asset.get("size") or 0),
                            file_name=str(asset.get("name") or ""),
                        )
                    )
                if len(payload) < 100:
                    break
            if releases:
                releases.sort(key=lambda r: r.sort_key, reverse=True)
                cache_releases("dxvk", releases)
                return releases
            log.info("GitHub API returned no usable DXVK releases; using the feed")
        except (net.NetworkError, ValueError) as exc:
            log.info("GitHub API listing failed (%s); falling back to the release feed", exc)

        # jsDelivr carries the complete tag list, so it comes before the feed:
        # the feed only ever publishes the ten newest releases.
        try:
            releases = _jsdelivr_releases()
            if releases:
                log.info("listing came from jsDelivr (%s tags)", len(releases))
                cache_releases("dxvk", releases)
                return releases
        except (net.NetworkError, ValueError, AttributeError) as exc:
            log.warning("jsDelivr listing failed: %s", exc)

        try:
            releases = _atom_dxvk_releases()
            if releases:
                # Merge with whatever is cached: the feed is only a window of
                # recent releases and must not drop the older ones.
                known = {item.version: item for item in cached_releases("dxvk")}
                for item in releases:
                    known[item.version] = item
                merged = sorted(known.values(), key=lambda r: r.sort_key, reverse=True)
                cache_releases("dxvk", merged)
                return merged
        except (net.NetworkError, ValueError) as exc:
            log.warning("release feed listing failed: %s", exc)

    return cached_releases("dxvk")


_GPLASYNC_RE = re.compile(r"dxvk-gplasync-v?([0-9.]+(?:-[0-9]+)?)\.tar\.gz$")


def fetch_gplasync_releases(*, allow_network: bool = True) -> list[Release]:
    """DXVK-gplasync packages from the GitLab repository tree.

    Falls back to the cached listing when GitLab is unreachable, which happens
    regularly on filtered connections.
    """
    releases: list[Release] = []
    if not allow_network:
        return cached_releases("gplasync")
    page = 1
    while page <= 10:
        try:
            payload = net.get_json(GITLAB_TREE.format(page=page))
        except (net.NetworkError, ValueError) as exc:
            log.warning("gplasync listing failed on page %s: %s", page, exc)
            break
        if not isinstance(payload, list) or not payload:
            break
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if not name.endswith(".tar.gz") or "native" in name:
                continue
            match = _GPLASYNC_RE.search(name)
            version = f"v{match.group(1)}" if match else name[: -len(".tar.gz")]
            releases.append(
                Release(
                    kind="gplasync",
                    version=version,
                    label=f"DXVK-gplasync {version}",
                    url=GITLAB_RAW.format(name=name),
                    date="",
                    size=0,
                    file_name=name,
                )
            )
        if len(payload) < 100:
            break
        page += 1
    releases.sort(key=lambda r: r.sort_key, reverse=True)
    if releases:
        cache_releases("gplasync", releases)
        return releases
    return cached_releases("gplasync")


def version_dir(kind: str, version: str) -> Path:
    """Directory that holds one extracted version."""
    folder = safe_name(version.lstrip("v") if kind == "gplasync" else version)
    return cache_dir(kind) / folder


def list_installed(kind: str) -> list[str]:
    """Version folder names that exist in the cache."""
    root = cache_dir(kind)
    try:
        return sorted(
            (child.name for child in root.iterdir() if child.is_dir()),
            key=parse_version_tuple,
            reverse=True,
        )
    except OSError:
        return []


def is_installed(kind: str, version: str) -> bool:
    return version_dir(kind, version).is_dir()


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _safe_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    members: list[tarfile.TarInfo] = []
    root = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if not str(target).startswith(str(root)):
            log.warning("skipping unsafe archive member: %s", member.name)
            continue
        members.append(member)
    return members


def extract_archive(archive_path: Path, destination: Path) -> None:
    """Extract a tar.gz package, refusing members that escape the target."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = _safe_members(archive, destination)
        try:
            archive.extractall(destination, members=members, filter="data")
        except TypeError:  # Python < 3.12
            archive.extractall(destination, members=members)


def find_bin_root(base: Path) -> Path | None:
    """Locate the folder that directly contains x32/x64 inside an extraction."""
    if not base.is_dir():
        return None
    if all((base / arch).is_dir() for arch in ARCH_FOLDERS):
        return base
    try:
        children = [child for child in base.iterdir() if child.is_dir()]
    except OSError:
        return None
    for child in children:
        if all((child / arch).is_dir() for arch in ARCH_FOLDERS):
            return child
    for child in children:
        nested = find_bin_root(child)
        if nested is not None:
            return nested
    return None


def arch_bin_dir(kind: str, version: str, arch: str) -> Path | None:
    """Path to the x32 or x64 folder of an installed version."""
    base = version_dir(kind, version)
    root = find_bin_root(base)
    if root is None:
        return None
    candidate = root / arch
    return candidate if candidate.is_dir() else None


def list_dlls(kind: str, version: str, arch: str) -> list[str]:
    folder = arch_bin_dir(kind, version, arch)
    if folder is None:
        return []
    try:
        return sorted(child.name for child in folder.iterdir() if child.suffix.lower() == ".dll")
    except OSError:
        return []


def reference_conf(kind: str, version: str) -> Path | None:
    """The dxvk.conf shipped inside a downloaded package, when present."""
    base = version_dir(kind, version)
    if not base.is_dir():
        return None
    for candidate in (base / "dxvk.conf", base / "dxvk.conf.sample"):
        if candidate.is_file():
            return candidate
    try:
        for child in base.iterdir():
            if child.is_dir():
                nested = child / "dxvk.conf"
                if nested.is_file():
                    return nested
    except OSError:
        pass
    return None


def download_release(
    release: Release,
    *,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Download and extract a release; returns the folder holding the DLLs."""
    target = version_dir(release.kind, release.version)
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)

    file_name = release.file_name or Path(release.url).name or f"{release.kind}.tar.gz"
    archive = archives_dir() / f"{release.kind}-{safe_name(file_name)}"
    last_error: Exception | None = None
    try:
        for url in download_candidates(release.url):
            try:
                net.http_download(url, archive, progress=progress, cancel=cancel, timeout=120)
                if cancel is not None and cancel.is_set():
                    raise net.Cancelled("cancelled")
                extract_archive(archive, target)
                if url != release.url:
                    log.info("downloaded %s through a mirror: %s", release.version, url)
                break
            except net.Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - try the next source
                last_error = exc
                log.warning("download attempt failed (%s): %s", url, exc)
                shutil.rmtree(target, ignore_errors=True)
                target.mkdir(parents=True, exist_ok=True)
        else:
            raise net.NetworkError(
                f"所有下载源都失败了，最后一个错误：{last_error}"
            )
    finally:
        if not settings.get("keep_archive", False):
            try:
                archive.unlink()
            except OSError:
                pass

    root = find_bin_root(target)
    if root is None:
        raise net.NetworkError(
            "the downloaded package does not contain x32/x64 folders - it may be corrupt"
        )
    log.info("installed %s %s into %s", release.kind, release.version, target)
    return root


def remove_version(kind: str, version: str) -> None:
    shutil.rmtree(version_dir(kind, version), ignore_errors=True)


REFERENCE_URL = "https://raw.githubusercontent.com/doitsujin/dxvk/{ref}/dxvk.conf"


def references_dir() -> Path:
    folder = data_root() / "references"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def fetch_reference_conf(ref: str = "master") -> Path:
    """Download the option reference for a tag (zlib licensed, upstream DXVK)."""
    clean = safe_name(ref or "master")
    target = references_dir() / f"dxvk-{clean}.conf"
    body = net.http_get(REFERENCE_URL.format(ref=ref or "master"), timeout=30, retries=2)
    if b"dxvk." not in body:
        raise net.NetworkError(f"{ref} does not look like a DXVK configuration reference")
    target.write_bytes(body)
    log.info("saved reference for %s to %s", ref, target)
    return target


def installed_size(kind: str, version: str) -> int:
    total = 0
    for path in version_dir(kind, version).rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total
