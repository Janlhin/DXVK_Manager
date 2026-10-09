"""Resilient HTTP helpers built on the standard library.

The application must work on machines behind flaky links or a local proxy, so
every request is attempted with urllib first (direct, then through a proxy) and
finally falls back to the curl binary that ships with Windows 10+.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import settings
from .util import log

USER_AGENT = "DXVK-Version-Manager-Py/1.0 (+https://github.com/artmakh/dxvk-version-mananger)"

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


class NetworkError(RuntimeError):
    """Raised when every transport failed for a URL."""


class Cancelled(RuntimeError):
    """Raised when the user cancelled an in-flight operation."""


def system_proxy() -> str:
    """Read the WinINET proxy (the one the Windows settings dialog writes)."""
    if os.name != "nt":
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            if os.environ.get(key):
                return os.environ[key]
        return ""
    try:
        import winreg  # noqa: WPS433 - Windows only

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return ""
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            server = str(server or "").strip()
    except (OSError, ImportError, ValueError):
        return ""
    if not server:
        return ""
    if "=" in server:
        # e.g. "http=127.0.0.1:7897;https=127.0.0.1:7897"
        parts = dict(
            chunk.split("=", 1) for chunk in server.split(";") if "=" in chunk
        )
        server = parts.get("https") or parts.get("http") or ""
    server = server.strip()
    if not server:
        return ""
    return server if "://" in server else "http://" + server


def _proxy_candidates(force_proxy: str | None = None) -> list[str | None]:
    """Ordered list of proxies to try for the current settings."""
    if force_proxy is not None:
        return [force_proxy or None]
    mode = str(settings.get("proxy_mode") or "auto")
    custom = str(settings.get("proxy_url") or "").strip()
    if mode == "direct":
        return [None]
    if mode == "custom" and custom:
        return [custom, None]
    discovered = system_proxy()
    if discovered:
        return [None, discovered]
    return [None]


def _curl_binary() -> str | None:
    found = shutil.which("curl") or shutil.which("curl.exe")
    if found:
        return found
    fallback = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    return str(fallback) if fallback.exists() else None


def _opener(proxy: str | None):
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _urllib_get(url: str, proxy: str | None, timeout: float, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers={**headers, "User-Agent": USER_AGENT})
    with _opener(proxy).open(request, timeout=timeout) as response:
        return response.read()


def _curl_get(url: str, proxy: str | None, timeout: float, headers: dict[str, str]) -> bytes:
    binary = _curl_binary()
    if not binary:
        raise NetworkError("curl is not available")
    command = [
        binary,
        "-sS",
        "-L",
        "--max-time",
        str(int(max(10, timeout))),
        "-A",
        USER_AGENT,
    ]
    for name, value in headers.items():
        command += ["-H", f"{name}: {value}"]
    if proxy:
        command += ["--proxy", proxy]
    completed = subprocess.run(command + [url], capture_output=True)
    if completed.returncode != 0:
        raise NetworkError(
            f"curl failed with code {completed.returncode}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    return completed.stdout


def offline() -> bool:
    """True when the user asked the application to stay off the network."""
    return bool(settings.get("offline_mode"))


def _refuse_offline(url: str) -> None:
    if offline():
        raise NetworkError(f"离线模式已开启，已阻止请求：{url}")


def http_get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    headers: dict[str, str] | None = None,
    force_proxy: str | None = None,
) -> bytes:
    """GET a URL and return the raw body, trying every transport in turn."""
    _refuse_offline(url)
    extra_headers = dict(headers or {})
    last_error: Exception | None = None
    proxies = _proxy_candidates(force_proxy)

    for attempt in range(max(1, retries)):
        for proxy in proxies:
            try:
                return _urllib_get(url, proxy, timeout, extra_headers)
            except Exception as exc:  # noqa: BLE001 - transport errors vary wildly
                last_error = exc
                log.debug("urllib GET failed (%s, proxy=%s): %s", url, proxy, exc)
        for proxy in proxies:
            try:
                return _curl_get(url, proxy, timeout, extra_headers)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log.debug("curl GET failed (%s, proxy=%s): %s", url, proxy, exc)
        if attempt + 1 < retries:
            time.sleep(0.6 * (attempt + 1))
    raise NetworkError(f"GET {url} failed: {last_error}")


def get_json(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    headers: dict[str, str] | None = None,
) -> Any:
    merged = {"Accept": "application/json", **(headers or {})}
    body = http_get(url, timeout=timeout, retries=retries, headers=merged)
    return json.loads(body.decode("utf-8", "replace"))


def _curl_download(
    url: str,
    destination: Path,
    proxy: str | None,
    timeout: float,
    progress: Callable[[int, int], None] | None,
    cancel: threading.Event | None,
) -> int:
    binary = _curl_binary()
    if not binary:
        raise NetworkError("curl is not available")
    command = [
        binary,
        "-sS",
        "-L",
        "--max-time",
        str(int(max(30, timeout))),
        "-A",
        USER_AGENT,
        "-o",
        str(destination),
    ]
    if proxy:
        command += ["--proxy", proxy]
    command.append(url)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    total = 0
    while process.poll() is None:
        if cancel is not None and cancel.is_set():
            process.kill()
            raise Cancelled("download cancelled")
        size = destination.stat().st_size if destination.exists() else 0
        if progress and size != total:
            total = size
            progress(size, 0)
        time.sleep(0.3)
    if process.returncode != 0:
        stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        raise NetworkError(f"curl download failed: {stderr.strip()[:200]}")
    return destination.stat().st_size if destination.exists() else 0


def http_download(
    url: str,
    destination: str | os.PathLike[str],
    *,
    timeout: float = 60.0,
    progress: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
    force_proxy: str | None = None,
) -> int:
    """Stream a URL to a file. Returns the number of bytes written.

    progress receives (downloaded_bytes, total_bytes); total is 0 when the
    server does not report a content length. Raises Cancelled when the cancel
    event is set, and NetworkError when no transport worked.
    """
    _refuse_offline(url)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    proxies = _proxy_candidates(force_proxy)
    last_error: Exception | None = None

    for proxy in proxies:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with _opener(proxy).open(request, timeout=timeout) as response:
                try:
                    total = int(response.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    total = 0
                written = 0
                with target.open("wb") as fh:
                    while True:
                        if cancel is not None and cancel.is_set():
                            raise Cancelled("download cancelled")
                        chunk = response.read(262144)
                        if not chunk:
                            break
                        fh.write(chunk)
                        written += len(chunk)
                        if progress:
                            progress(written, total)
                return written
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.debug("urllib download failed (%s, proxy=%s): %s", url, proxy, exc)

    for proxy in proxies:
        try:
            return _curl_download(url, target, proxy, timeout, progress, cancel)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.debug("curl download failed (%s, proxy=%s): %s", url, proxy, exc)

    raise NetworkError(f"download {url} failed: {last_error}")


def check_connectivity(timeout: float = 8.0) -> bool:
    try:
        http_get("https://api.github.com/rate_limit", timeout=timeout, retries=1)
        return True
    except Exception:  # noqa: BLE001
        return False
