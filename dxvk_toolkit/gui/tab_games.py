"""Installed games: detection, DXVK install, restore and removal."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Any

from .. import covers, installer, metadata, sources, steam
from ..paths import settings
from ..util import human_size, log, open_in_file_manager
from . import theme
from .covergrid import CardSpec, CoverGrid
from .tasks import bind_progress
from .widgets import ModalDialog, SearchEntry, Tooltip, TreePanel

STATUS_LABELS = {
    "patched": "已安装 DXVK",
    "clean": "原生 / 未修改",
    "backup": "有备份可还原",
}


class GamesTab(ttk.Frame):
    """Steam (and manually added) games with one-click DXVK management."""

    def __init__(self, app: Any) -> None:
        super().__init__(app, style="TFrame", padding=(20, 16))
        self.app = app
        self.games: list[steam.Game] = []
        self.loaded_once = False
        self._scanning = False
        self._detecting = False
        self.detection: dict[str, dict[str, str]] = {}
        self.statuses: dict[str, installer.GameStatus] = {}
        self.pcgw: dict[str, str] = {}
        self.only_patched = tk.BooleanVar(value=False)
        self.view_mode = str(settings.get("games_view") or "grid")
        self.loader = covers.CoverLoader(self)
        self.platform_filter = tk.StringVar(value="")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, style="TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="已安装游戏", style="H1.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="自动读取 Steam 库（含所有库文件夹）与手动添加的目录，识别 Direct3D 版本与架构。",
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="重新扫描", style="Accent.TButton",
                   command=lambda: self.refresh(force=True)).grid(row=0, column=1, rowspan=2,
                                                                  sticky="e", padx=(8, 0))

        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(14, 8))
        toolbar.columnconfigure(2, weight=1)
        self.search = SearchEntry(toolbar, placeholder="搜索游戏…",
                                  on_change=lambda _t: self._render(), width=26)
        self.search.grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(toolbar, text="仅显示已安装 DXVK", variable=self.only_patched,
                        command=self._render).grid(row=0, column=1, padx=(12, 0))
        self.count_label = ttk.Label(toolbar, text="", style="Muted.TLabel")
        self.count_label.grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="添加游戏文件夹…", command=self.add_manual_game).grid(row=0,
                                                                                      column=3,
                                                                                      sticky="e")
        views = ttk.Frame(toolbar, style="TFrame")
        views.grid(row=0, column=4, sticky="e", padx=(10, 0))
        self.grid_button = ttk.Button(views, text="卡片", width=6,
                                      command=lambda: self._set_view("grid"))
        self.grid_button.grid(row=0, column=0)
        self.list_button = ttk.Button(views, text="列表", width=6,
                                      command=lambda: self._set_view("list"))
        self.list_button.grid(row=0, column=1, padx=(4, 0))
        self._sync_view_buttons()

        self.tree = TreePanel(
            self,
            [
                ("name", "游戏", 300, "w"),
                ("appid", "AppID", 80, "w"),
                ("d3d", "Direct3D", 130, "w"),
                ("arch", "架构", 60, "w"),
                ("state", "DXVK 状态", 150, "w"),
                ("conf", "dxvk.conf", 90, "w"),
            ],
            height=12,
            on_select=lambda _iid: self._update_details(),
            on_double_click=lambda _iid: self.open_apply_dialog(),
        )
        self.tree.grid(row=3, column=0, sticky="nsew")

        self.grid_view = CoverGrid(
            self,
            loader=self.loader,
            on_select=self._select_key,
            on_activate=lambda _key: self.open_apply_dialog(),
        )
        self.grid_view.grid(row=3, column=0, sticky="nsew")
        if self.view_mode != "grid":
            self.grid_view.grid_remove()
        else:
            self.tree.grid_remove()

        self.chips = ttk.Frame(self, style="TFrame")
        self.chips.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        details = ttk.Frame(self, style="Surface.TFrame", padding=14)
        details.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        details.columnconfigure(1, weight=1)
        self.detail_title = ttk.Label(details, text="选择一款游戏查看详情", style="H2.TLabel",
                                      background=theme.SURFACE)
        self.detail_title.grid(row=0, column=0, columnspan=2, sticky="w")
        self.detail_body = ttk.Label(details, text="", style="MutedSurface.TLabel", justify="left",
                                     wraplength=860)
        self.detail_body.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))

        buttons = ttk.Frame(details, style="Surface.TFrame")
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.apply_button = ttk.Button(buttons, text="应用 DXVK…", style="Accent.TButton",
                                       command=self.open_apply_dialog)
        self.apply_button.grid(row=0, column=0)
        ttk.Button(buttons, text="还原原始 DLL", command=self.restore_selected).grid(row=0, column=1,
                                                                                   padx=(8, 0))
        ttk.Button(buttons, text="移除 DXVK", command=self.remove_selected).grid(row=0, column=2,
                                                                                padx=(8, 0))
        ttk.Button(buttons, text="打开游戏目录",
                   command=self.reveal_selected).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(buttons, text="编辑该游戏的 dxvk.conf",
                   command=self.edit_conf_for_selected).grid(row=0, column=4, padx=(8, 0))

        self._selected_iid = ""

    # -- lifecycle -------------------------------------------------------
    def on_show(self) -> None:
        if not self.loaded_once:
            self.refresh()

    def refresh(self, *, force: bool = False) -> None:
        if self._scanning:
            return
        self._scanning = True
        self.app.notify("正在扫描 Steam 库…")
        manual = list(settings.get("manual_games") or [])
        extra = list(settings.get("steam_extra_libraries") or [])

        def work(task: Any) -> tuple[list[steam.Game], dict[str, installer.GameStatus]]:
            found = steam.scan_steam_games(extra)
            known = {game.key for game in found}
            for entry in manual:
                game = steam.Game.from_dict(entry) if isinstance(entry, dict) else None
                if game and game.key not in known:
                    found.append(game)
                    known.add(game.key)
            # Reading folder state costs a directory listing plus signature
            # probes, so it happens here instead of inside a repaint.
            statuses: dict[str, installer.GameStatus] = {}
            candidates = [game for game in found if game.exists]
            for index, game in enumerate(candidates):
                if task.cancelled:
                    break
                statuses[game.key] = installer.inspect(game.install_dir)
                if index % 5 == 0:
                    task.set_progress(
                        (index + 1) / max(1, len(candidates)),
                        f"正在读取游戏状态 {index + 1}/{len(candidates)}",
                    )
            return found, statuses

        def done(payload: tuple[list[steam.Game], dict[str, installer.GameStatus]]) -> None:
            games, statuses = payload
            self._scanning = False
            self.loaded_once = True
            self.app.progress(None, "")
            self.games = games
            self.statuses.update(statuses)
            self._render_chips()
            # Shared with the config tab, which lists games as write targets.
            self.app.state["games"] = games
            self._render()
            installed = sum(1 for g in games if g.exists)
            self.app.notify(f"发现 {len(games)} 款游戏（{installed} 个目录可用）", "ok")
            # Phase two: identify Direct3D / architecture without blocking the UI.
            self._start_detection(games)

        def failed(exc: Exception) -> None:
            self._scanning = False
            self.app.notify(f"扫描失败：{exc}", "error")

        task = self.app.runner.submit("scan-games", work, on_done=done, on_error=failed)
        bind_progress(task, lambda fraction, text: self.app.progress(fraction, text))

    def _start_detection(self, games: list[steam.Game]) -> None:
        """Identify Direct3D family and architecture for every game folder."""
        if self._detecting:
            return
        targets = [game for game in games if game.exists]
        if not targets:
            return
        self._detecting = True

        def work(task: Any) -> None:
            for index, game in enumerate(targets):
                if task.cancelled:
                    return
                info = steam.describe_game(game.install_dir, persist=False)
                self.detection[game.key] = info
                if index % 6 == 0:
                    task.set_progress((index + 1) / len(targets),
                                      f"正在识别 {index + 1}/{len(targets)}")

        def done(_result: Any) -> None:
            self._detecting = False
            steam.flush_detect_cache()
            self.app.progress(None, "")
            self._render()
            unknown = sum(
                1 for game in targets if self.detection.get(game.key, {}).get("direct3d")
                in ("", "Unknown")
            )
            self.app.notify(
                f"识别完成：{len(targets) - unknown}/{len(targets)} 款游戏已确定 Direct3D 版本", "ok"
            )
            self._start_pcgw(targets)

        task = self.app.runner.submit("detect-games", work, on_done=done)
        bind_progress(task, lambda fraction, text: self.app.progress(fraction, text))

    def _start_pcgw(self, games: list[steam.Game]) -> None:
        """Ask PCGamingWiki about the games we could not identify locally.

        Everything is cached on disk for weeks, lookups are capped per pass and
        failures are silent - the tab works fine without any network.
        """
        pending = [
            game
            for game in games
            if game.appid.isdigit()
            and self.detection.get(game.key, {}).get("direct3d") in ("", "Unknown")
            and self.pcgw.get(game.key, "") == ""
        ][:12]
        if not pending:
            return

        def work(_task: Any) -> dict[str, str]:
            found: dict[str, str] = {}
            for game in pending:
                data = metadata.get(game.appid)
                value = str(data.get("direct3d") or "").strip()
                if value:
                    found[game.key] = value
            return found

        def done(found: dict[str, str]) -> None:
            if not found:
                return
            self.pcgw.update(found)
            self._render()
            self.app.notify(f"已从 PCGamingWiki 补充 {len(found)} 款游戏的兼容性信息", "ok")

        self.app.runner.submit("pcgw-metadata", work, on_done=done)

    # -- rendering -------------------------------------------------------
    def _status_for(self, game: steam.Game) -> installer.GameStatus:
        """Cached folder state; never probes the disk during a repaint."""
        cached = self.statuses.get(game.key)
        if cached is not None:
            return cached
        status = installer.inspect(game.install_dir, probe=False)
        self.statuses[game.key] = status
        return status

    def _refresh_status(self, game: steam.Game) -> None:
        """Re-read one folder after we changed it (still off the UI thread)."""
        game_dir = game.install_dir

        def work(_task: Any) -> installer.GameStatus:
            installer.invalidate(game_dir)
            return installer.inspect(game_dir)

        def done(status: installer.GameStatus) -> None:
            self.statuses[game.key] = status
            self._render()

        self.app.runner.submit("refresh-status", work, on_done=done)

    def _detected(self, game: steam.Game) -> tuple[str, str]:
        """(Direct3D label, architecture) for display."""
        info = self.detection.get(game.key)
        d3d = (info or {}).get("direct3d") or ""
        arch = (info or {}).get("arch") or ""
        if not d3d or d3d == "Unknown":
            fallback = self.pcgw.get(game.key, "")
            if fallback:
                d3d = fallback if fallback.lower().startswith("direct3d") else f"Direct3D {fallback}"
        if not arch:
            arch = self._status_for(game).arch
        if not d3d:
            d3d = "检测中…" if self._detecting else "Unknown"
        return d3d, arch or "未知"

    def _render(self) -> None:
        """Rebuild whichever view is active (both read the same cached data)."""
        term = self.search.value.lower()
        platform = self.platform_filter.get()
        rows: list[tuple[steam.Game, installer.GameStatus, str, str, str, list[str]]] = []
        patched = 0
        for game in self.games:
            if term and term not in f"{game.name} {game.appid}".lower():
                continue
            if platform and game.source != platform:
                continue
            if not game.exists:
                rows.append((game, installer.GameStatus(install_dir=str(game.install_dir)),
                             "-", "-", "目录不存在", ["muted"]))
                continue
            status = self._status_for(game)
            d3d, arch = self._detected(game)
            if status.patched:
                state_text = f"已安装 {status.kind or 'dxvk'} {status.version}".strip()
                tags = ["patched"]
                patched += 1
            elif status.backuped:
                state_text = "有备份，可还原"
                tags = ["warn"]
            else:
                state_text = "原生 / 未修改"
                tags = []
            if self.only_patched.get() and not status.patched:
                continue
            rows.append((game, status, d3d, arch, state_text, tags))

        if self.view_mode == "grid":
            self._render_grid(rows)
        else:
            self._render_tree(rows)
        self.count_label.configure(
            text=f"{len(rows)} / {len(self.games)} 款（{patched} 款已装 DXVK）"
        )
        self._update_details()

    def _render_tree(self, rows: list[tuple[Any, ...]]) -> None:
        self.tree.clear()
        for game, status, d3d, arch, state_text, tags in rows:
            conf = "已存在" if status.conf_present else "-"
            self.tree.add_row(
                [game.name, game.appid, d3d, arch, state_text, conf],
                iid=game.key,
                tags=tags,
            )
        if self._selected_iid:
            try:
                self.tree.tree.selection_set(self._selected_iid)
            except tk.TclError:
                self._selected_iid = ""

    def _render_grid(self, rows: list[tuple[Any, ...]]) -> None:
        specs: list[CardSpec] = []
        for game, status, d3d, arch, state_text, _tags in rows:
            if status.patched:
                badge, kind = state_text, "ok"
            elif status.backuped:
                badge, kind = "可还原", "warn"
            elif not game.exists:
                badge, kind = "目录缺失", "error"
            else:
                badge, kind = "未安装", "muted"
            subtitle = f"{d3d} · {arch}" if d3d not in ("-", "") else ""
            specs.append(
                CardSpec(
                    key=game.key,
                    title=game.name,
                    platform=game.source,
                    platform_label=game.platform_label,
                    subtitle=subtitle,
                    status=badge,
                    status_kind=kind,
                    urls=covers.source_urls(game),
                    tooltip=str(game.install_dir),
                )
            )
        self.grid_view.set_specs(specs)
        if self._selected_iid:
            self.grid_view.select(self._selected_iid)

    def _sync_view_buttons(self) -> None:
        grid_active = self.view_mode == "grid"
        self.grid_button.configure(style="Accent.TButton" if grid_active else "TButton")
        self.list_button.configure(style="TButton" if grid_active else "Accent.TButton")

    def _render_chips(self) -> None:
        """Platform filters, built from the platforms actually present."""
        for child in self.chips.winfo_children():
            child.destroy()
        platforms: list[str] = []
        for game in self.games:
            if game.source not in platforms:
                platforms.append(game.source)
        if len(platforms) <= 1:
            return
        options = [("", f"全部 {len(self.games)}")] + [
            (source, f"{steam.PLATFORM_LABELS.get(source, source.title())} "
                     f"{sum(1 for g in self.games if g.source == source)}")
            for source in platforms
        ]
        for index, (value, label) in enumerate(options):
            active = self.platform_filter.get() == value
            button = ttk.Button(
                self.chips,
                text=label,
                style="Accent.TButton" if active else "Ghost.TButton",
                command=lambda v=value: self._set_platform(v),
            )
            button.grid(row=0, column=index, padx=(0, 6))

    def _set_platform(self, value: str) -> None:
        self.platform_filter.set(value)
        self._render_chips()
        self._render()

    def _set_view(self, mode: str) -> None:
        if mode == self.view_mode:
            return
        self.view_mode = mode
        settings.set("games_view", mode)
        self._sync_view_buttons()
        if mode == "grid":
            self.tree.grid_remove()
            self.grid_view.grid()
        else:
            self.grid_view.grid_remove()
            self.tree.grid()
        self._render()

    def _game_for_selection(self) -> steam.Game | None:
        key = self._selected_iid
        if not key:
            return None
        for game in self.games:
            if game.key == key:
                return game
        return None

    def _select_key(self, key: str) -> None:
        self._selected_iid = key
        self._update_details()

    def _update_details(self) -> None:
        game = self._game_for_selection()
        self._selected_iid = game.key if game else ""
        if game is None:
            self.detail_title.configure(text="选择一款游戏查看详情")
            self.detail_body.configure(text="")
            return
        status = self._status_for(game)
        d3d, arch = self._detected(game)
        source = "Steam 库" if game.source == "steam" else "手动添加"
        if game.key in self.pcgw and d3d == self.pcgw.get(game.key):
            source += "（Direct3D 信息来自 PCGamingWiki）"
        lines = [
            f"路径：{game.install_dir}",
            f"来源：{source}" + (f"    库文件夹：{game.library_dir}" if game.library_dir else ""),
            f"Direct3D：{d3d}    架构：{arch}    "
            f"计划安装：{', '.join(installer.dlls_for_direct3d(d3d).required)}",
        ]
        if status.patched:
            lines.append(
                f"当前状态：{status.kind or 'dxvk'} {status.version}（{status.timestamp or '时间未知'}）"
            )
        else:
            lines.append("当前状态：未安装 DXVK")
        if status.backup_files:
            lines.append(f"备份文件：{', '.join(name + '.bkp' for name in status.backup_files)}")
        lines.append(f"dxvk.conf：{'已存在' if status.conf_present else '无'}")
        if game.size_on_disk:
            lines.append(f"占用空间：{human_size(game.size_on_disk)}")
        self.detail_title.configure(text=game.name)
        self.detail_body.configure(text="\n".join(lines))

    # -- actions ---------------------------------------------------------
    def add_manual_game(self) -> None:
        folder = filedialog.askdirectory(title="选择游戏目录（包含游戏 exe 的文件夹）")
        if not folder:
            return
        game = steam.game_from_folder(folder)
        existing = {steam.Game.from_dict(e).key for e in (settings.get("manual_games") or [])
                    if isinstance(e, dict)}
        if game.key in existing:
            self.app.notify("该目录已在列表中", "warn")
            return
        entries = list(settings.get("manual_games") or [])
        entries.append(game.to_dict())
        settings.set("manual_games", entries)
        self.app.notify(f"已添加 {game.name}", "ok")
        self.refresh(force=True)

    def reveal_selected(self) -> None:
        game = self._game_for_selection()
        if game is None:
            self.app.notify("请先选择一款游戏", "warn")
            return
        open_in_file_manager(game.install_dir if game.install_dir.exists() else game.install_dir.parent)

    def edit_conf_for_selected(self) -> None:
        game = self._game_for_selection()
        if game is None:
            self.app.notify("请先选择一款游戏", "warn")
            return
        config_tab = self.app.tab("config")
        if config_tab is None:
            return
        config_tab.focus_game(game)
        self.app.show_tab("config")

    def restore_selected(self) -> None:
        game = self._game_for_selection()
        if game is None:
            self.app.notify("请先选择一款游戏", "warn")
            return
        status = installer.inspect(game.install_dir)
        if not status.backup_files:
            self.app.notify("该游戏没有可还原的备份", "warn")
            return
        if not self.app.ask_yes_no("还原原始 DLL", f"将 {game.name} 的 DXVK 文件替换回原始备份，继续？"):
            return

        def work(_task: Any) -> Any:
            return installer.restore(game.install_dir)

        def done(result: Any) -> None:
            self.app.notify(result.message, "ok" if result.success else "warn")
            self._refresh_status(game)

        self.app.runner.submit(
            "restore", work, on_done=done, on_error=lambda exc: self.app.notify(str(exc), "error")
        )

    def remove_selected(self) -> None:
        game = self._game_for_selection()
        if game is None:
            self.app.notify("请先选择一款游戏", "warn")
            return
        if not self.app.ask_yes_no(
            "移除 DXVK",
            f"将删除 {game.name} 中的 DXVK DLL（备份文件会保留，可随时还原），继续？",
        ):
            return

        def work(_task: Any) -> Any:
            return installer.remove_dxvk(game.install_dir)

        def done(removed: Any) -> None:
            self.app.notify(f"已移除 {len(removed)} 个 DXVK 文件", "ok" if removed else "warn")
            self._refresh_status(game)

        self.app.runner.submit(
            "remove", work, on_done=done, on_error=lambda exc: self.app.notify(str(exc), "error")
        )

    def open_apply_dialog(self) -> None:
        game = self._game_for_selection()
        if game is None:
            self.app.notify("请先选择一款游戏", "warn")
            return
        if not game.exists:
            self.app.notify("游戏目录不存在", "error")
            return
        d3d, arch = self._detected(game)
        ApplyDxvkDialog(
            self.app,
            game,
            on_finished=lambda: self._refresh_status(game),
            d3d_hint="" if d3d in ("检测中…",) else d3d,
            arch_hint="" if arch in ("未知", "") else arch,
        ).show()


class ApplyDxvkDialog(ModalDialog):
    """Choose a cached version, architecture and DLL set for one game."""

    def __init__(
        self,
        app: Any,
        game: steam.Game,
        *,
        on_finished: Any = None,
        d3d_hint: str = "",
        arch_hint: str = "",
    ) -> None:
        super().__init__(app, f"为 {game.name} 安装 DXVK", width=680, height=520)
        self.app = app
        self.game = game
        self.on_finished = on_finished
        self.values: list[tuple[str, str, str]] = []  # (label, kind, version)

        ttk.Label(self.body, text=game.name, style="H2.TLabel").pack(anchor="w")
        ttk.Label(
            self.body,
            text=str(game.install_dir),
            style="Muted.TLabel",
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        for kind in ("dxvk", "gplasync"):
            for version in sources.list_installed(kind):
                self.values.append(
                    (f"{'官方 DXVK' if kind == 'dxvk' else 'GPLAsync'}  {version}", kind, version)
                )

        if not self.values:
            ttk.Label(
                self.body,
                text="本地还没有已下载的 DXVK 版本。\n请先到「DXVK 版本」页下载一个版本，再回来安装。",
                style="Warn.TLabel",
                justify="left",
            ).pack(anchor="w", pady=10)
            ttk.Button(self.body, text="关闭", command=self.close).pack(anchor="e", pady=(16, 0))
            return

        form = ttk.Frame(self.body, style="TFrame")
        form.pack(fill="x", pady=(4, 10))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="DXVK 版本").grid(row=0, column=0, sticky="w", pady=4)
        self.version_var = tk.StringVar(value=self.values[0][0])
        combo = ttk.Combobox(form, textvariable=self.version_var, state="readonly",
                             values=[label for label, _k, _v in self.values])
        combo.grid(row=0, column=1, sticky="ew", pady=4)

        d3d_guess = d3d_hint or steam.guess_direct3d(game.install_dir)
        if d3d_guess not in ("Direct3D 8", "Direct3D 9", "Direct3D 10", "Direct3D 11",
                             "Direct3D 12", "Unknown"):
            d3d_guess = "Unknown"
        ttk.Label(form, text="Direct3D").grid(row=1, column=0, sticky="w", pady=4)
        self.d3d_var = tk.StringVar(value=d3d_guess)
        ttk.Combobox(form, textvariable=self.d3d_var, state="readonly",
                     values=["Direct3D 8", "Direct3D 9", "Direct3D 10", "Direct3D 11",
                             "Direct3D 12", "Unknown"]).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="架构").grid(row=2, column=0, sticky="w", pady=4)
        self.arch_var = tk.StringVar(value=arch_hint or installer.choose_arch(game.install_dir))
        ttk.Combobox(form, textvariable=self.arch_var, state="readonly",
                     values=["x64", "x32"]).grid(row=2, column=1, sticky="ew", pady=4)

        self.include_conf = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form,
            text="同时写入当前 DXVK 配置页生成的 dxvk.conf",
            variable=self.include_conf,
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))

        plan = installer.dlls_for_direct3d(d3d_guess)
        ttk.Label(
            self.body,
            text="将安装：" + ", ".join(plan.required) + f"（{plan.description}）",
            style="Muted.TLabel",
        ).pack(anchor="w")

        self.status = ttk.Label(self.body, text="", style="Muted.TLabel", wraplength=620,
                                justify="left")
        self.status.pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(self.body, style="TFrame")
        buttons.pack(side="bottom", fill="x", pady=(16, 0))
        self.install_button = ttk.Button(buttons, text="开始安装", style="Accent.TButton",
                                         command=self._install)
        self.install_button.pack(side="right")
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right", padx=(0, 8))

        self.d3d_var.trace_add("write", lambda *_a: self._refresh_plan())
        self.arch_var.trace_add("write", lambda *_a: self._refresh_plan())

    def _selected_release(self) -> tuple[str, str]:
        label = self.version_var.get()
        for text, kind, version in self.values:
            if text == label:
                return kind, version
        return self.values[0][1], self.values[0][2]

    def _refresh_plan(self) -> None:
        plan = installer.dlls_for_direct3d(self.d3d_var.get())
        self.status.configure(
            text=f"将复制 {', '.join(plan.required)} ({plan.description})，架构 {self.arch_var.get()}"
        )

    def _install(self) -> None:
        kind, version = self._selected_release()
        d3d = self.d3d_var.get()
        arch = self.arch_var.get()
        conf_text = None
        if self.include_conf.get():
            generator = self.app.tab("config")
            if generator is not None:
                conf_text = generator.current_text()
            if not conf_text:
                conf_text = "# Generated by DXVK Version Manager\n"
        self.install_button.configure(state="disabled")
        self.status.configure(text="正在安装…")
        game = self.game

        def work(_task: Any) -> Any:
            return installer.install(
                game.install_dir, kind, version, arch=arch, d3d_hint=d3d, conf_text=conf_text
            )

        def done(result: Any) -> None:
            self.install_button.configure(state="normal")
            if result.success:
                self.status.configure(text=result.message)
                self.app.notify(result.message, "ok")
                if callable(self.on_finished):
                    self.on_finished()
                self.after(600, self.close)
            else:
                self.status.configure(text=result.message)
                self.app.notify(result.message, "error")

        def failed(exc: Exception) -> None:
            self.install_button.configure(state="normal")
            self.status.configure(text=str(exc))
            self.app.notify(f"安装失败：{exc}", "error")

        self.app.runner.submit("apply-dxvk", work, on_done=done, on_error=failed)
