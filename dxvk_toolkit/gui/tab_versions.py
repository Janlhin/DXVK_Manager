"""DXVK / DXVK-gplasync version browser and downloader."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .. import net, sources
from ..paths import cache_dir
from ..util import human_size, log, open_in_file_manager
from . import theme
from .tasks import bind_progress
from .widgets import SearchEntry, TreePanel

KIND_INFO = {
    "dxvk": {
        "title": "DXVK 版本",
        "subtitle": "来自 doitsujin/dxvk 的官方发布版本。下载后即可安装到游戏目录。",
        "empty": "尚未下载任何 DXVK 版本。",
    },
    "gplasync": {
        "title": "DXVK-GPLAsync 版本",
        "subtitle": "来自 GitLab 上 Ph42oN/dxvk-gplasync 的 async 分支，适合需要异步编译的游戏。",
        "empty": "尚未下载任何 DXVK-GPLAsync 版本。",
    },
}


class VersionsTab(ttk.Frame):
    """Lists remote releases and locally cached versions for one DXVK flavour."""

    def __init__(self, app: Any, *, kind: str = "dxvk") -> None:
        super().__init__(app, style="TFrame", padding=(20, 16))
        self.app = app
        self.kind = kind
        self.info = KIND_INFO[kind]
        self.releases: list[sources.Release] = []
        self.loaded_once = False
        self._busy = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, style="TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=self.info["title"], style="H1.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=self.info["subtitle"], style="Muted.TLabel",
                  wraplength=760, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="刷新列表", style="Accent.TButton",
                   command=lambda: self.refresh(force=True)).grid(row=0, column=1, rowspan=2,
                                                                  sticky="e", padx=(8, 0))

        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(14, 8))
        toolbar.columnconfigure(1, weight=1)
        self.search = SearchEntry(toolbar, placeholder="搜索版本…",
                                  on_change=lambda _text: self._render(), width=26)
        self.search.grid(row=0, column=0, sticky="w")
        self.count_label = ttk.Label(toolbar, text="", style="Muted.TLabel")
        self.count_label.grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="打开缓存目录", style="Ghost.TButton",
                   command=lambda: open_in_file_manager(cache_dir(self.kind))).grid(row=0, column=2,
                                                                                   sticky="e")

        self.tree = TreePanel(
            self,
            [
                ("version", "版本", 140, "w"),
                ("date", "发布日期", 110, "w"),
                ("size", "大小", 90, "e"),
                ("state", "本地状态", 130, "w"),
                ("kind", "类型", 110, "w"),
            ],
            height=14,
            on_double_click=lambda _iid: self._on_row_activate(),
        )
        self.tree.grid(row=3, column=0, sticky="nsew")
        self.tree.tree.bind("<Return>", lambda _e: self._on_row_activate())

        actions = ttk.Frame(self, style="TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.download_button = ttk.Button(actions, text="下载所选版本", style="Accent.TButton",
                                          command=self.download_selected)
        self.download_button.grid(row=0, column=0)
        ttk.Button(actions, text="删除本地副本", command=self.delete_selected).grid(row=0, column=1,
                                                                                 padx=(8, 0))
        ttk.Button(actions, text="在资源管理器中显示",
                   command=self.reveal_selected).grid(row=0, column=2, padx=(8, 0))
        self.hint = ttk.Label(actions, text="双击列表项可直接下载", style="Muted.TLabel")
        self.hint.grid(row=0, column=3, sticky="e", padx=(12, 0))
        actions.columnconfigure(3, weight=1)

    # -- lifecycle -------------------------------------------------------
    def on_show(self) -> None:
        if not self.loaded_once:
            self.refresh()

    # -- data ------------------------------------------------------------
    def refresh(self, *, force: bool = False) -> None:
        if self._busy:
            return
        self._busy = True
        self.app.notify(f"正在获取 {self.info['title']} 列表…")
        kind = self.kind

        def work(_task: Any) -> list[sources.Release]:
            if kind == "dxvk":
                return sources.fetch_dxvk_releases()
            return sources.fetch_gplasync_releases()

        def done(releases: list[sources.Release]) -> None:
            self._busy = False
            self.loaded_once = True
            self.releases = releases
            self._render()
            if releases:
                self.app.notify(f"已获取 {len(releases)} 个版本", "ok")
            else:
                self.app.notify("无法获取版本列表（网络不可用或接口受限）", "warn")

        def failed(exc: Exception) -> None:
            self._busy = False
            self.app.notify(f"获取版本列表失败：{exc}", "error")

        self.app.runner.submit(f"releases-{kind}", work, on_done=done, on_error=failed)

    def _render(self) -> None:
        term = self.search.value.lower()
        self.tree.clear()
        installed = set(sources.list_installed(self.kind))
        shown = 0
        for release in self.releases:
            label = f"{release.version.lstrip('v') if self.kind == 'gplasync' else release.version}"
            if term and term not in (release.version + " " + release.label).lower():
                continue
            local = self.kind == "gplasync" and release.version.lstrip("v") in installed
            local = local or (self.kind == "dxvk" and release.version in installed)
            tags = ["patched"] if local else []
            self.tree.add_row(
                [
                    label,
                    release.date or "-",
                    human_size(release.size) if release.size else "-",
                    "已下载" if local else "未下载",
                    "GPLAsync" if self.kind == "gplasync" else "官方 DXVK",
                ],
                iid=f"{release.kind}:{release.version}",
                tags=tags,
            )
            shown += 1
        suffix = f"（已筛选，共 {len(self.releases)} 个）" if term else f"共 {len(self.releases)} 个"
        self.count_label.configure(text=f"{shown} {suffix}")

    def _release_for_selection(self) -> sources.Release | None:
        iid = self.tree.selected
        if not iid:
            return None
        _, _, version = iid.partition(":")
        for release in self.releases:
            if release.version == version:
                return release
        return None

    # -- actions ---------------------------------------------------------
    def _on_row_activate(self) -> None:
        release = self._release_for_selection()
        if release is None:
            return
        if self._is_local(release):
            self.reveal_selected()
        else:
            self.start_download(release)

    def _is_local(self, release: sources.Release) -> bool:
        installed = set(sources.list_installed(self.kind))
        name = release.version.lstrip("v") if self.kind == "gplasync" else release.version
        return name in installed

    def download_selected(self) -> None:
        release = self._release_for_selection()
        if release is None:
            self.app.notify("请先选择一个版本", "warn")
            return
        self.start_download(release)

    def start_download(self, release: sources.Release) -> None:
        if self._is_local(release):
            self.app.notify(f"{release.version} 已在本地", "info")
            return
        self.download_button.configure(state="disabled")
        self.app.notify(f"开始下载 {release.label}…")

        def work(task: Any) -> Any:
            def progress(done_bytes: int, total_bytes: int) -> None:
                if task.cancelled:
                    return
                fraction = (done_bytes / total_bytes) if total_bytes else 0.0
                task.set_progress(
                    fraction,
                    f"{human_size(done_bytes)} / {human_size(total_bytes) if total_bytes else '?'}",
                )

            return sources.download_release(release, progress=progress, cancel=task.cancel_event)

        def done(path: Any) -> None:
            self.download_button.configure(state="normal")
            self.app.progress(None, "")
            self.app.notify(f"{release.version} 下载完成并已解压", "ok")
            self._render()

        def failed(exc: Exception) -> None:
            self.download_button.configure(state="normal")
            self.app.progress(None, "")
            if isinstance(exc, net.Cancelled):
                self.app.notify("下载已取消", "warn")
            else:
                self.app.notify(f"下载失败：{exc}", "error")

        task = self.app.runner.submit(
            f"download-{release.version}", work, on_done=done, on_error=failed
        )
        bind_progress(task, lambda fraction, text: self.app.progress(fraction, text))

    def delete_selected(self) -> None:
        iid = self.tree.selected
        if not iid:
            self.app.notify("请先选择一个版本", "warn")
            return
        _, _, version = iid.partition(":")
        installed = set(sources.list_installed(self.kind))
        name = version.lstrip("v") if self.kind == "gplasync" else version
        if name not in installed:
            self.app.notify("该版本不在本地", "warn")
            return
        if not self.app.ask_yes_no("删除本地副本", f"确定删除本地缓存的 {version} 吗？"):
            return
        sources.remove_version(self.kind, version)
        self.app.notify(f"已删除本地副本 {version}", "ok")
        self._render()

    def reveal_selected(self) -> None:
        iid = self.tree.selected
        if not iid:
            open_in_file_manager(cache_dir(self.kind))
            return
        _, _, version = iid.partition(":")
        path = sources.version_dir(self.kind, version)
        open_in_file_manager(path if path.exists() else cache_dir(self.kind))
