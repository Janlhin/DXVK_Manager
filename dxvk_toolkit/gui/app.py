"""Main window: sidebar navigation, content area and shared services."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .. import APP_EDITION, APP_NAME, APP_VERSION
from ..paths import asset_path, data_root, settings
from ..util import log, setup_logging
from . import theme
from .tasks import TaskRunner
from .widgets import StatusBar

NAV_ITEMS = (
    ("versions", "DXVK 版本", "下载与管理官方 DXVK 版本"),
    ("gplasync", "GPLAsync 版本", "带 async 补丁的 DXVK 分支"),
    ("games", "已安装游戏", "检测 Steam 游戏并安装 / 还原 DXVK"),
    ("config", "DXVK 配置", "生成 dxvk.conf 并写入游戏目录"),
    ("settings", "设置", "网络、参考文件与数据目录"),
)


class DxvkManagerApp(tk.Tk):
    """The application window."""

    def __init__(self) -> None:
        super().__init__()
        setup_logging()
        self.title(f"{APP_NAME} · {APP_EDITION} {APP_VERSION}")
        self.minsize(1080, 680)
        geometry = str(settings.get("window_geometry") or "")
        self.geometry(geometry if "x" in geometry else "1280x800")
        self.configure(background=theme.BG)

        theme.apply_theme(self)
        self.runner = TaskRunner(self)

        # Shared state between tabs.
        self.state: dict[str, Any] = {
            "games": [],
            "config_values": {},
            "config_model": None,
            "selected_game_dir": "",
        }
        self._tabs: dict[str, ttk.Frame] = {}
        self._factories: dict[str, Any] = {}
        self._nav_buttons: dict[str, ttk.Button] = {}
        self._current = ""

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, lambda: self.show_tab("games"))

    # -- layout ----------------------------------------------------------
    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, style="Surface.TFrame", width=210)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(len(NAV_ITEMS) + 1, weight=1)

        brand = ttk.Frame(sidebar, style="Surface.TFrame", padding=(16, 18, 16, 12))
        brand.grid(row=0, column=0, sticky="ew")
        ttk.Label(brand, text="DXVK", style="H1.TLabel", background=theme.SURFACE).pack(anchor="w")
        ttk.Label(brand, text="Version Manager · Python", style="MutedSurface.TLabel").pack(anchor="w")

        for index, (key, label, hint) in enumerate(NAV_ITEMS, start=1):
            button = ttk.Button(
                sidebar,
                text=label,
                style="Nav.TButton",
                command=lambda name=key: self.show_tab(name),
            )
            button.grid(row=index, column=0, sticky="ew", padx=8, pady=2)
            self._nav_buttons[key] = button

        footer = ttk.Frame(sidebar, style="Surface.TFrame", padding=(16, 10))
        footer.grid(row=len(NAV_ITEMS) + 2, column=0, sticky="ew")
        ttk.Label(footer, text=f"v{APP_VERSION}", style="MutedSurface.TLabel").pack(anchor="w")
        ttk.Label(
            footer,
            text=f"数据目录:\n{data_root()}",
            style="MutedSurface.TLabel",
            wraplength=170,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.content = ttk.Frame(self, style="TFrame")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.status = StatusBar(self)
        self.status.grid(row=1, column=1, sticky="ew")

    def register_tab(self, key: str, frame: ttk.Frame) -> None:
        self._tabs[key] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()

    def register_lazy_tab(self, key: str, factory: Any) -> None:
        """Defer building a page until it is first opened (faster startup)."""
        self._factories[key] = factory

    def tab(self, key: str) -> ttk.Frame | None:
        """The page for a key, building it on first use."""
        frame = self._tabs.get(key)
        if frame is None and key in self._factories:
            frame = self._factories[key]()
            self.register_tab(key, frame)
        return frame

    # -- navigation ------------------------------------------------------
    def show_tab(self, key: str) -> None:
        if self.tab(key) is None:
            return
        if self._current and self._current in self._tabs:
            self._tabs[self._current].grid_remove()
            self._nav_buttons[self._current].configure(style="Nav.TButton")
        self._tabs[key].grid()
        self._nav_buttons[key].configure(style="NavActive.TButton")
        self._current = key
        on_show = getattr(self._tabs[key], "on_show", None)
        if callable(on_show):
            on_show()

    # -- helpers ---------------------------------------------------------
    def notify(self, text: str, kind: str = "info") -> None:
        self.status.set_status(text, kind)
        log.debug("status: %s", text)

    def progress(self, fraction: float | None, text: str = "") -> None:
        self.status.show_progress(fraction, text)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self))

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self)

    def _on_close(self) -> None:
        try:
            settings.set("window_geometry", self.geometry())
        except Exception:  # noqa: BLE001
            pass
        games_tab = self._tabs.get("games")
        loader = getattr(games_tab, "loader", None)
        if loader is not None:
            loader.shutdown()
        self.runner.stop()
        self.destroy()


def build_app() -> DxvkManagerApp:
    """Create the window with every tab registered."""
    from .tab_config import ConfigTab
    from .tab_games import GamesTab
    from .tab_settings import SettingsTab
    from .tab_versions import VersionsTab

    app = DxvkManagerApp()
    # Pages are built the first time they are shown: constructing all five up
    # front costs a few hundred milliseconds that the user feels at startup.
    app.register_lazy_tab("games", lambda: GamesTab(app))
    app.register_lazy_tab("versions", lambda: VersionsTab(app, kind="dxvk"))
    app.register_lazy_tab("gplasync", lambda: VersionsTab(app, kind="gplasync"))
    app.register_lazy_tab("config", lambda: ConfigTab(app))
    app.register_lazy_tab("settings", lambda: SettingsTab(app))
    return app


def run() -> int:
    try:
        app = build_app()
    except Exception as exc:  # noqa: BLE001
        log.error("failed to start the UI: %s", exc)
        print(f"Failed to start the UI: {exc}", file=sys.stderr)
        return 1
    app.mainloop()
    return 0
