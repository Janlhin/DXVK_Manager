"""Background work so the UI thread never blocks on network or disk IO."""

from __future__ import annotations

import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from ..util import log


@dataclass
class Task:
    """Handle for one unit of background work."""

    name: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _progress: tuple[float, str] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    finished: bool = False

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> None:
        self.cancel_event.set()

    def set_progress(self, fraction: float, text: str = "") -> None:
        with self._lock:
            self._progress = (max(0.0, min(1.0, float(fraction))), text)


class TaskRunner:
    """Thread pool plus a queue that is drained on the Tk main loop.

    Every callback runs in the UI thread, so widgets may be touched freely
    from on_done / on_error / on_progress.
    """

    def __init__(self, root: Any, workers: int = 6, interval_ms: int = 60) -> None:
        self._root = root
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dxvk-task")
        self._events: "queue.Queue[tuple[str, Any, Any]]" = queue.Queue()
        self._interval = interval_ms
        self._active: list[Task] = []
        self._stopped = False
        # The timer id is kept so stop() can cancel a callback that is still
        # queued; otherwise it fires against a destroyed widget after close.
        self._timer: str | None = self._root.after(self._interval, self._drain)

    # -- public API ------------------------------------------------------
    def submit(
        self,
        name: str,
        work: Callable[[Task], Any],
        *,
        on_done: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        on_finally: Callable[[], None] | None = None,
    ) -> Task:
        task = Task(name=name)
        with threading.Lock():
            self._active.append(task)

        def run() -> None:
            try:
                result = work(task)
            except Exception as exc:  # noqa: BLE001 - reported through the queue
                log.debug("task %s failed: %s\n%s", name, exc, traceback.format_exc())
                task.finished = True
                self._events.put(("error", task, (exc, on_error, on_finally)))
            else:
                task.finished = True
                self._events.put(("done", task, (result, on_done, on_finally)))

        self._pool.submit(run)
        return task

    def stop(self) -> None:
        self._stopped = True
        if self._timer is not None:
            try:
                self._root.after_cancel(self._timer)
            except Exception:  # noqa: BLE001 - the interpreter may be gone already
                pass
            self._timer = None
        for task in list(self._active):
            task.cancel()
        self._pool.shutdown(wait=False, cancel_futures=True)

    # -- internals -------------------------------------------------------
    def _drain(self) -> None:
        self._timer = None
        if self._stopped:
            return
        while True:
            try:
                kind, task, payload = self._events.get_nowait()
            except queue.Empty:
                break
            try:
                if task in self._active:
                    self._active.remove(task)
            except ValueError:
                pass
            if kind == "done":
                result, on_done, on_finally = payload
                if on_done and not task.cancelled:
                    self._guard(on_done, result)
            else:
                exc, on_error, on_finally = payload
                if on_error and not task.cancelled:
                    self._guard(on_error, exc)
            if on_finally:
                self._guard(on_finally)

        for task in list(self._active):
            with task._lock:
                progress = task._progress
                task._progress = None
            if progress and not task.cancelled:
                handler = getattr(task, "progress_handler", None)
                if handler:
                    self._guard(handler, progress[0], progress[1])
        try:
            self._timer = self._root.after(self._interval, self._drain)
        except Exception:  # noqa: BLE001 - window closed
            self._stopped = True

    @staticmethod
    def _guard(callback: Callable[..., Any], *args: Any) -> None:
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 - a broken callback must not kill the pump
            log.error("UI callback failed: %s", traceback.format_exc())


def bind_progress(task: Task, handler: Callable[[float, str], None]) -> Task:
    """Attach a progress handler to a task handle (read by the pump)."""
    setattr(task, "progress_handler", handler)
    return task
