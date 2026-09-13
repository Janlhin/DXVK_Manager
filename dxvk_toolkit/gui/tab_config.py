"""The DXVK configuration generator: pick options, preview, write dxvk.conf."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Any

from .. import confbuild, confspec, installer, steam
from ..paths import asset_path, settings
from ..util import log, open_in_file_manager
from . import theme
from .widgets import (
    ModalDialog,
    ScrollFrame,
    SearchEntry,
    Tooltip,
    set_readonly_text,
)


class _OptionRow:
    """One reusable option row (checkbox + label + value entry)."""

    __slots__ = ("frame", "check", "label", "entry", "enabled_var", "value_var",
                 "tooltip", "group", "trace_ids")

    def __init__(
        self,
        frame: ttk.Frame,
        check: ttk.Checkbutton,
        label: ttk.Label,
        entry: ttk.Entry,
        enabled_var: tk.BooleanVar,
        value_var: tk.StringVar,
        tooltip: Tooltip,
    ) -> None:
        self.frame = frame
        self.check = check
        self.label = label
        self.entry = entry
        self.enabled_var = enabled_var
        self.value_var = value_var
        self.tooltip = tooltip
        self.group: confspec.OptionGroup | None = None
        self.trace_ids: list[tuple[Any, str]] = []


class ConfigTab(ttk.Frame):
    """Generates dxvk.conf from the reference option catalogue."""

    def __init__(self, app: Any) -> None:
        super().__init__(app, style="TFrame", padding=(20, 16))
        self.app = app
        self.model: confspec.ConfModel | None = None
        self.values: dict[str, Any] = {}
        self.rows: list[tuple[confspec.OptionGroup, tk.BooleanVar, tk.StringVar, ttk.Entry]] = []
        self._row_pool: list[_OptionRow] = []
        self._headers: list[ttk.Label] = []
        self._prewarm_timer: str | None = None
        self.target_game_dir = ""
        self._preview_after: str | None = None
        self._rendered_basic: bool | None = None

        self.columnconfigure(0, weight=3, minsize=520)
        self.columnconfigure(1, weight=2, minsize=360)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, style="TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="DXVK 配置生成器", style="H1.TLabel").grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(
            header,
            text="选项来自 DXVK 官方 dxvk.conf 参考文件，勾选后生成可用的 dxvk.conf。",
            style="Muted.TLabel",
            wraplength=780,
            justify="left",
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="重新载入参考文件", command=self.reload_model).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(8, 0)
        )

        toolbar = ttk.Frame(self, style="TFrame")
        toolbar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        toolbar.columnconfigure(2, weight=1)
        self.search = SearchEntry(toolbar, placeholder="搜索选项（如 hud、frame rate）…",
                                  on_change=lambda _t: self.render_options(), width=32)
        self.search.grid(row=0, column=0, sticky="w")
        self.advanced_var = tk.BooleanVar(value=bool(settings.get("show_advanced")))
        ttk.Checkbutton(toolbar, text="显示高级选项", variable=self.advanced_var,
                        command=self._toggle_advanced).grid(row=0, column=1, padx=(12, 0))
        self.count_label = ttk.Label(toolbar, text="", style="Muted.TLabel")
        self.count_label.grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.options_panel = ScrollFrame(self, background=theme.BG)
        self.options_panel.grid(row=3, column=0, sticky="nsew", padx=(0, 14))
        self.empty_label = ttk.Label(
            self.options_panel.inner, text="没有匹配的选项", style="Muted.TLabel"
        )

        side = ttk.Frame(self, style="Surface.TFrame", padding=14)
        side.grid(row=3, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(3, weight=1)
        ttk.Label(side, text="dxvk.conf 预览", style="H2.TLabel",
                  background=theme.SURFACE).grid(row=0, column=0, sticky="w")
        self.selection_label = ttk.Label(side, text="尚未选择任何选项", style="MutedSurface.TLabel")
        self.selection_label.grid(row=1, column=0, sticky="w", pady=(2, 8))

        text_frame = ttk.Frame(side, style="Surface.TFrame")
        text_frame.grid(row=3, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.preview = tk.Text(text_frame, width=44, height=24, wrap="none",
                               background=theme.SURFACE_ALT, foreground=theme.TEXT,
                               insertbackground=theme.TEXT, relief="flat", padx=10, pady=8,
                               font=theme.fonts().mono, highlightthickness=1,
                               highlightbackground=theme.BORDER)
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.preview.configure(state="disabled")
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(side, style="Surface.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        for index, (label, command, style) in enumerate(
            (
                ("复制", self.copy_to_clipboard, "TButton"),
                ("导出为文件…", self.export_conf, "TButton"),
                ("写入游戏目录…", self.write_to_game, "Accent.TButton"),
            )
        ):
            ttk.Button(actions, text=label, command=command, style=style).grid(
                row=0, column=index, padx=(0, 6)
            )

        self.notice = ttk.Label(side, text="", style="MutedSurface.TLabel", wraplength=330,
                                justify="left")
        self.notice.grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Button(side, text="清空全部选择", style="Ghost.TButton",
                   command=self.reset_values).grid(row=6, column=0, sticky="w", pady=(8, 0))

    # -- lifecycle -------------------------------------------------------
    def on_show(self) -> None:
        if self.model is None:
            self.reload_model()

    def reload_model(self, path: Path | None = None) -> None:
        model = confspec.load_model(path)
        self.model = model
        label = str(model.source_path) if model.source_path else "未找到参考文件"
        self.subtitle.configure(
            text=f"共 {model.option_count} 个可配置项，来源：{label}"
        )
        self._rendered_basic = None
        self.render_options()
        self.schedule_preview()

    def _toggle_advanced(self) -> None:
        settings.set("show_advanced", bool(self.advanced_var.get()))
        self._rendered_basic = None
        self.render_options()

    # -- option list -----------------------------------------------------
    def render_options(self) -> None:
        """Show the matching options, reusing the existing row widgets.

        Building eighty-odd rows of six widgets each costs a couple of hundred
        milliseconds - very visible while typing in the search box - so rows
        and section headers are pooled and simply rebound.
        """
        if self.model is None:
            return
        basic_only = not self.advanced_var.get()
        term = self.search.value
        groups = self.model.filter(term, basic_only=basic_only, current=self.values)

        panel = self.options_panel
        panel.begin_bulk()
        for row in self._row_pool:
            row.frame.pack_forget()
        for header in self._headers:
            header.pack_forget()

        self.rows = []
        if not groups:
            self.empty_label.pack(anchor="w", pady=12)
        else:
            self.empty_label.pack_forget()
            header_index = 0
            current_section = ""
            for index, group in enumerate(groups):
                section = group.members[0].section
                if section != current_section:
                    current_section = section
                    header = self._header_at(header_index)
                    header.configure(text=f"[{section}]")
                    header.pack(anchor="w", pady=(14, 4))
                    header_index += 1
                row = self._row_at(index)
                self._bind_row(row, group)
                row.frame.pack(fill="x", pady=2)

        panel.end_bulk()
        if basic_only and self.model is not None:
            # Create the remaining rows during idle time so switching to the
            # advanced view is instant instead of pausing for ~0.4 s.
            self._prewarm_pool(self.model.option_count)
        self._rendered_basic = basic_only
        shown = len(groups)
        self.count_label.configure(
            text=f"显示 {shown} / {self.model.option_count} 项"
            + ("（基础模式）" if basic_only else "（高级模式）")
        )
        panel.scroll_to_top()

    # -- widget pool -----------------------------------------------------
    def _prewarm_pool(self, target: int, chunk: int = 5) -> None:
        """Grow the row pool in small idle slices."""
        self._prewarm_timer = None
        try:
            if not self.winfo_exists() or len(self._row_pool) >= target:
                return
            for _ in range(min(chunk, target - len(self._row_pool))):
                self._row_pool.append(self._create_row())
            if len(self._row_pool) < target:
                self._prewarm_timer = self.after(12, lambda: self._prewarm_pool(target, chunk))
        except tk.TclError:
            self._prewarm_timer = None

    def _header_at(self, index: int) -> ttk.Label:
        while len(self._headers) <= index:
            self._headers.append(ttk.Label(self.options_panel.inner, text="", style="H2.TLabel"))
        return self._headers[index]

    def _row_at(self, index: int) -> "_OptionRow":
        while len(self._row_pool) <= index:
            self._row_pool.append(self._create_row())
        return self._row_pool[index]

    def _create_row(self) -> "_OptionRow":
        frame = ttk.Frame(self.options_panel.inner, style="Surface.TFrame", padding=(10, 8))
        frame.columnconfigure(1, weight=1)
        enabled_var = tk.BooleanVar(value=False)
        value_var = tk.StringVar(value="")
        check = ttk.Checkbutton(frame, variable=enabled_var, style="Surface.TCheckbutton")
        check.grid(row=0, column=0, sticky="w", padx=(0, 8))
        label = ttk.Label(frame, text="", style="Surface.TLabel")
        label.grid(row=0, column=1, sticky="w")
        entry = ttk.Entry(frame, textvariable=value_var, width=18)
        entry.grid(row=0, column=2, sticky="e", padx=(8, 0))
        tooltip = Tooltip(frame, "", wraplength=680)
        Tooltip(label, "", wraplength=680)
        return _OptionRow(frame, check, label, entry, enabled_var, value_var, tooltip)

    def _bind_row(self, row: "_OptionRow", group: confspec.OptionGroup) -> None:
        for var, trace_id in row.trace_ids:
            try:
                var.trace_remove("write", trace_id)
            except (tk.TclError, ValueError):
                pass
        row.trace_ids = []

        stored = self.values.get(group.key)
        if group.type == "boolean":
            enabled = bool(stored)
            value = "True"
        else:
            enabled = stored is not None and str(stored).strip() != ""
            value = str(stored) if enabled else ""

        row.enabled_var.set(enabled)
        row.value_var.set(value)
        row.label.configure(text=group.label)
        row.group = group

        placeholder = self._placeholder(group)
        description = group.description()
        row.tooltip.update_text(
            description + (f"\n\n默认示例: {placeholder}" if placeholder else "")
        )

        if group.type == "boolean":
            row.value_var.set("True / 未设置")
            row.entry.configure(state="disabled", width=14)
        else:
            row.entry.configure(state="normal", width=18)
            row.entry.configure(foreground=theme.TEXT if enabled else theme.TEXT_DIM)

        row.trace_ids = [
            (
                row.enabled_var,
                row.enabled_var.trace_add("write", lambda *_a, item=row: self._on_toggle(item)),
            ),
            (
                row.value_var,
                row.value_var.trace_add("write", lambda *_a, item=row: self._on_value(item)),
            ),
        ]
        if enabled and group.type != "boolean":
            self.values[group.key] = value
        self.rows.append((group, row.enabled_var, row.value_var, row.entry))

    def _on_toggle(self, row: "_OptionRow") -> None:
        group = row.group
        if group is None:
            return
        if group.type == "boolean":
            self.values[group.key] = True if row.enabled_var.get() else None
        elif row.enabled_var.get():
            row.entry.configure(foreground=theme.TEXT)
            if not row.value_var.get():
                row.value_var.set(self._placeholder(group))
            self.values[group.key] = row.value_var.get()
        else:
            row.entry.configure(foreground=theme.TEXT_DIM)
            self.values[group.key] = None
        self.schedule_preview()

    def _on_value(self, row: "_OptionRow") -> None:
        group = row.group
        if group is None or group.type == "boolean":
            return
        if row.enabled_var.get():
            self.values[group.key] = row.value_var.get()
        self.schedule_preview()

    @staticmethod
    def _placeholder(group: confspec.OptionGroup) -> str:
        example = (group.example or "").strip()
        if example.startswith('"') and example.endswith('"') and len(example) >= 2:
            return example[1:-1]
        if example in ("True", "False"):
            return ""
        return example

    # -- preview ---------------------------------------------------------
    def schedule_preview(self) -> None:
        if self._preview_after:
            try:
                self.after_cancel(self._preview_after)
            except tk.TclError:
                pass
        self._preview_after = self.after(280, self.refresh_preview)

    def refresh_preview(self) -> None:
        self._preview_after = None
        text = self.current_text()
        set_readonly_text(self.preview, text)
        active = confbuild.selection_summary(self.values)
        self.selection_label.configure(text=active)
        if self.target_game_dir:
            self.notice.configure(text=f"将写入：{self.target_game_dir}")
        else:
            self.notice.configure(
                text="提示：dxvk.conf 需要与游戏 exe 放在同一目录；"
                "可在此直接点击「写入游戏目录…」。"
            )

    def current_text(self) -> str:
        if self.model is None:
            return ""
        return confbuild.build_conf(
            self.model.groups, self.values, section_order=self.model.section_order
        )

    def reset_values(self) -> None:
        self.values = {}
        self.render_options()
        self.schedule_preview()

    # -- actions ---------------------------------------------------------
    def copy_to_clipboard(self) -> None:
        text = self.current_text()
        self.app.clipboard_clear()
        self.app.clipboard_append(text)
        self.app.notify("dxvk.conf 内容已复制到剪贴板", "ok")

    def export_conf(self) -> None:
        text = self.current_text()
        initial_dir = str(settings.get("last_export_dir") or os.path.expanduser("~"))
        target = filedialog.asksaveasfilename(
            title="导出 dxvk.conf",
            initialdir=initial_dir,
            initialfile="dxvk.conf",
            defaultextension=".conf",
            filetypes=[("DXVK 配置", "*.conf"), ("所有文件", "*.*")],
        )
        if not target:
            return
        try:
            Path(target).write_text(text, encoding="utf-8", newline="\r\n")
        except OSError as exc:
            self.app.notify(f"写入失败：{exc}", "error")
            return
        settings.set("last_export_dir", str(Path(target).parent))
        self.app.notify(f"已导出到 {target}", "ok")

    def write_to_game(self) -> None:
        dialog = PickGameDialog(self.app, self.target_game_dir)
        chosen = dialog.show()
        if not chosen:
            return
        try:
            path = installer.write_conf(chosen, self.current_text())
        except OSError as exc:
            self.app.notify(f"写入失败：{exc}", "error")
            return
        self.target_game_dir = chosen
        self.refresh_preview()
        self.app.notify(f"已写入 {path}", "ok")

    def focus_game(self, game: steam.Game) -> None:
        """Called when the user jumps here from the games list."""
        self.target_game_dir = str(game.install_dir)
        self.refresh_preview()
        self.app.notify(f"目标游戏：{game.name}")


class PickGameDialog(ModalDialog):
    """Pick a game folder to write dxvk.conf into."""

    def __init__(self, app: Any, current: str = "") -> None:
        super().__init__(app, "选择要写入 dxvk.conf 的游戏目录", width=680, height=520)
        self.app = app
        self.current = current
        self.selection = ""

        ttk.Label(self.body, text="选择游戏", style="H2.TLabel").pack(anchor="w")
        ttk.Label(
            self.body,
            text="dxvk.conf 会写入所选目录（与游戏 exe 同级）。也可以直接浏览到任意文件夹。",
            style="Muted.TLabel",
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        container = ttk.Frame(self.body, style="TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            container,
            background=theme.SURFACE,
            foreground=theme.TEXT,
            selectbackground=theme.ACCENT_DARK,
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=theme.BORDER,
            activestyle="none",
            font=theme.fonts().base,
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        self.dirs: list[str] = []
        games = list(self.app.state.get("games") or [])
        if not games:
            games = [g for g in steam.scan_steam_games() if g.exists]
        for game in sorted((g for g in games if g.exists), key=lambda g: g.name.lower()):
            self.dirs.append(str(game.install_dir))
            self.listbox.insert("end", f"{game.name}    -    {game.install_dir}")
        for entry in settings.get("manual_games") or []:
            if isinstance(entry, dict) and entry.get("install_dir"):
                path = str(entry["install_dir"])
                if path not in self.dirs and Path(path).is_dir():
                    self.dirs.append(path)
                    self.listbox.insert("end", f"[手动] {Path(path).name}    -    {path}")
        if self.current in self.dirs:
            index = self.dirs.index(self.current)
            self.listbox.selection_set(index)
            self.listbox.see(index)
        self.listbox.bind("<Double-1>", lambda _e: self._confirm())

        buttons = ttk.Frame(self.body, style="TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="浏览文件夹…", command=self._browse).pack(side="left")
        ttk.Button(buttons, text="写入", style="Accent.TButton", command=self._confirm).pack(
            side="right"
        )
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right", padx=(0, 8))

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="选择游戏目录（包含游戏 exe）")
        if folder:
            self.selection = folder
            self.result = folder
            self.close()

    def _confirm(self) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.selection = self.dirs[selection[0]]
        elif self.current:
            self.selection = self.current
        if self.selection:
            self.result = self.selection
            self.close()
