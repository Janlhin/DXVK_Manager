"""Thread pools, the busy indicator and in-flight task bookkeeping.

Every long operation in the UI goes through here: the pools keep slow work
(cover downloads, detection) away from the interface thread, the busy counter
keeps the spinner on until the *last* running task ends, and the pending sets
collapse duplicate requests for the same object.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


class JobService:
    """Shared worker-thread infrastructure for the bridge services."""

    def __init__(self, on_busy: Callable[[bool], None]) -> None:
        self._on_busy = on_busy
        # Two pools: identification must not queue behind cover downloads.
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qml-worker")
        self.detect_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qml-detect")
        # Name lookups hit the Steam store: keep them off the detection pool so
        # a slow network never delays the library scan.
        self.name_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qml-names")
        self._lock = threading.Lock()
        # Concurrent operations: the spinner must stay on until the last one
        # ends (a fast detect used to switch it off during a long download).
        self._busy_count = 0
        self._busy = False
        # In-flight task keys, grouped by purpose ("detect", "cover").
        self._pending: dict[str, set[str]] = {}

    # -- busy indicator --------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy(self, value: bool) -> None:
        """Track concurrent work; hide the indicator when the last task ends.

        A plain boolean let a fast task switch the spinner off while a long
        download was still running.
        """
        with self._lock:
            self._busy_count = max(0, self._busy_count + (1 if value else -1))
            busy = self._busy_count > 0
            changed = busy != self._busy
            self._busy = busy
        if changed:
            self._on_busy(busy)

    # -- in-flight bookkeeping -------------------------------------------
    def claim(self, group: str, key: str) -> bool:
        """Reserve ``key``; False when the same key is already in flight."""
        with self._lock:
            bucket = self._pending.setdefault(group, set())
            if key in bucket:
                return False
            bucket.add(key)
            return True

    def release(self, group: str, key: str) -> None:
        with self._lock:
            bucket = self._pending.get(group)
            if bucket is not None:
                bucket.discard(key)

    def pending(self, group: str) -> set[str]:
        with self._lock:
            return set(self._pending.get(group, ()))

    # -- shutdown --------------------------------------------------------
    def shutdown(self) -> None:
        for pool in (self.pool, self.detect_pool, self.name_pool):
            pool.shutdown(wait=False, cancel_futures=True)
