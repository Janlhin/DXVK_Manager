"""Settings: network, reference file, data locations and about."""

from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Any

from .. import APP_EDITION, APP_NAME, APP_VERSION, net, sources
from ..paths import archives_dir, asset_path, cache_dir, data_root, logs_dir, settings
from ..util import log, open_in_file_manager
from . import theme
from .widgets import hint_label

PROXY_MODES = (
    ("auto", "自动（先直连，失败后尝试系统代理）"),
    ("direct", "仅直连（不使用代理）"),
    ("custom", "自定义代理"),
)


class SettingsTab(ttk.Frame):
    """Application settings; everything is stored in settings.json."""

    def __init__(self, app: Any) -> None:
        super().__init__(app, style="TFrame", padding=(20, 16))
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="TFrame")
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="设置", style="H1.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=f"{APP_NAME} · {APP_EDITION} {APP_VERSION}",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        from .widgets import ScrollFrame

        scroller = ScrollFrame(self, background=theme.BG)
        scroller.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        body = scroller.inner
        body.columnconfigure(0, weight=1)

        self._build_network(body)
        self._build_reference(body)
        self._build_storage(body)
        self._build_about(body)

    # -- sections --------------------------------------------------------
    def _card(self, parent: tk.Misc, title: str, subtitle: str = "") -> ttk.Frame:
        card = ttk.Frame(parent, style="Surface.TFrame", padding=16)
        card.pack(fill="x", pady=(0, 14))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=title, style="H2.TLabel", background=theme.SURFACE).grid(
            row=0, column=0, sticky="w"
        )
        if subtitle:
            ttk.Label(card, text=subtitle, style="MutedSurface.TLabel", wraplength=860,
                      justify="left").grid(row=1, column=0, sticky="w", pady=(2, 10))
        return card

    def _build_network(self, parent: tk.Misc) -> None:
        card = self._card(
            parent,
            "网络",
            "下载 DXVK 与查询版本列表时使用。默认自动：先直连，失败后尝试 Windows 系统代理。",
        )
        row = ttk.Frame(card, style="Surface.TFrame")
        row.grid(row=2, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)

        mode = str(settings.get("proxy_mode") or "auto")
        self.proxy_mode = tk.StringVar(value=dict(PROXY_MODES).get(mode, PROXY_MODES[0][1]))
        ttk.Label(row, text="代理模式", style="MutedSurface.TLabel", width=12).grid(
            row=0, column=0, sticky="w", pady=4
        )
        combo = ttk.Combobox(row, textvariable=self.proxy_mode, state="readonly",
                             values=[label for _key, label in PROXY_MODES])
        combo.grid(row=0, column=1, sticky="ew", pady=4)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._save_proxy_mode())

        ttk.Label(row, text="代理地址", style="MutedSurface.TLabel", width=12).grid(
            row=1, column=0, sticky="w", pady=4
        )
        self.proxy_url = tk.StringVar(value=str(settings.get("proxy_url") or net.system_proxy()))
        entry = ttk.Entry(row, textvariable=self.proxy_url)
        entry.grid(row=1, column=1, sticky="ew", pady=4)
        entry.bind("<FocusOut>", lambda _e: settings.set("proxy_url", self.proxy_url.get().strip()))

        actions = ttk.Frame(card, style="Surface.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="测试连接", style="Accent.TButton",
                   command=self._test_connection).grid(row=0, column=0)
        ttk.Button(actions, text="使用系统代理地址",
                   command=self._use_system_proxy).grid(row=0, column=1, padx=(8, 0))
        self.net_status = ttk.Label(actions, text="", style="MutedSurface.TLabel")
        self.net_status.grid(row=0, column=2, padx=(12, 0))

    def _build_reference(self, parent: tk.Misc) -> None:
        card = self._card(
            parent,
            "选项参考文件（dxvk.conf）",
            "配置生成器的选项、说明与默认值都来自这个文件。默认使用随程序附带的 DXVK 官方参考文件"
            "（zlib 许可）；也可以改用自己下载的版本，或按 DXVK tag 在线获取。",
        )
        row = ttk.Frame(card, style="Surface.TFrame")
        row.grid(row=2, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)

        current = str(settings.get("reference_conf") or "")
        self.reference_var = tk.StringVar(value=current)
        ttk.Entry(row, textvariable=self.reference_var).grid(row=0, column=0, columnspan=2,
                                                             sticky="ew", pady=4)
        ttk.Button(row, text="浏览…", command=self._browse_reference).grid(row=0, column=2,
                                                                          padx=(8, 0))
        ttk.Button(row, text="使用内置参考文件",
                   command=self._use_bundled_reference).grid(row=1, column=0, sticky="w", pady=(4, 0))

        fetch_row = ttk.Frame(card, style="Surface.TFrame")
        fetch_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(fetch_row, text="按 DXVK tag 获取（如 v2.7.1 或 master）",
                  style="MutedSurface.TLabel").grid(row=0, column=0, sticky="w")
        self.tag_var = tk.StringVar(value="master")
        ttk.Entry(fetch_row, textvariable=self.tag_var, width=14).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(fetch_row, text="获取", command=self._fetch_reference).grid(row=0, column=2,
                                                                              padx=(8, 0))
        self.reference_status = ttk.Label(card, text="", style="MutedSurface.TLabel",
                                          wraplength=820, justify="left")
        self.reference_status.grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _build_storage(self, parent: tk.Misc) -> None:
        card = self._card(parent, "数据与缓存", "所有内容都保存在下面的目录，可随时清理。")
        holder = ttk.Frame(card, style="Surface.TFrame")
        holder.grid(row=2, column=0, sticky="ew")
        for label, path in (
            ("数据目录", data_root()),
            ("DXVK 缓存", cache_dir("dxvk")),
            ("GPLAsync 缓存", cache_dir("gplasync")),
            ("下载归档", archives_dir()),
            ("日志", logs_dir()),
        ):
            row = ttk.Frame(holder, style="Surface.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, style="MutedSurface.TLabel", width=14).pack(side="left")
            ttk.Label(row, text=str(path), style="Surface.TLabel").pack(side="left")
            ttk.Button(row, text="打开", style="Ghost.TButton",
                       command=lambda p=path: open_in_file_manager(p)).pack(side="right")

        actions = ttk.Frame(holder, style="Surface.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="清空版本缓存", command=self._clear_caches).pack(side="left")
        self.keep_archive = tk.BooleanVar(value=bool(settings.get("keep_archive")))
        ttk.Checkbutton(actions, text="保留下载的 .tar.gz 归档", variable=self.keep_archive,
                        style="Surface.TCheckbutton",
                        command=lambda: settings.set("keep_archive", self.keep_archive.get())).pack(
            side="left", padx=(12, 0)
        )

    def _build_about(self, parent: tk.Misc) -> None:
        card = self._card(parent, "关于", "")
        text = (
            f"{APP_NAME} · {APP_EDITION} {APP_VERSION}\n\n"
            "本程序是 artmakh/dxvk-version-mananger（MIT）的 Python 重写版，并内置了"
            " CamoMano/DXVK-Configurator（GPL-3.0）所演示的 dxvk.conf 生成功能。\n"
            "代码为独立实现，未复制上述项目的源代码；选项数据来自 doitsujin/dxvk 的"
            " dxvk.conf（zlib 许可）。\n\n"
            "DXVK 本身由 doitsujin 及贡献者开发；DXVK-gplasync 由 Ph42oN 维护。"
            "本工具只负责下载与安装，不修改这些项目的授权。"
        )
        holder = ttk.Frame(card, style="Surface.TFrame")
        holder.grid(row=2, column=0, sticky="ew")
        ttk.Label(holder, text=text, style="MutedSurface.TLabel", wraplength=860,
                  justify="left").pack(anchor="w")
        ttk.Button(holder, text="打开项目说明 (README)", style="Ghost.TButton",
                   command=self._open_readme).pack(anchor="w", pady=(10, 0))

    # -- actions ---------------------------------------------------------
    def _save_proxy_mode(self) -> None:
        label = self.proxy_mode.get()
        for key, text in PROXY_MODES:
            if text == label:
                settings.set("proxy_mode", key)
                self.app.notify(f"代理模式：{text}", "ok")
                return

    def _use_system_proxy(self) -> None:
        discovered = net.system_proxy()
        if discovered:
            self.proxy_url.set(discovered)
            settings.set("proxy_url", discovered)
            settings.set("proxy_mode", "custom")
            self.proxy_mode.set(dict(PROXY_MODES)["custom"])
            self.app.notify(f"已使用系统代理 {discovered}", "ok")
        else:
            self.app.notify("未在系统设置中发现代理", "warn")

    def _test_connection(self) -> None:
        settings.set("proxy_url", self.proxy_url.get().strip())
        self.net_status.configure(text="正在测试…", foreground=theme.TEXT_MUTED)

        def work(_task: Any) -> tuple[bool, str]:
            try:
                releases = sources.fetch_dxvk_releases(pages=1)
                return True, f"GitHub 可用（获取到 {len(releases)} 个版本）"
            except Exception as exc:  # noqa: BLE001
                return False, f"失败：{exc}"

        def done(result: tuple[bool, str]) -> None:
            ok, message = result
            self.net_status.configure(text=message,
                                      foreground=theme.OK if ok else theme.ERROR)
            self.app.notify(message, "ok" if ok else "error")

        self.app.runner.submit("net-test", work, on_done=done)

    def _browse_reference(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 dxvk.conf 参考文件",
            filetypes=[("DXVK 配置", "*.conf"), ("所有文件", "*.*")],
        )
        if not path:
            return
        settings.set("reference_conf", path)
        self.reference_var.set(path)
        self._apply_reference_change(f"已切换参考文件：{path}")

    def _use_bundled_reference(self) -> None:
        settings.set("reference_conf", "")
        self.reference_var.set("")
        self._apply_reference_change(f"已使用内置参考文件：{asset_path('dxvk.conf')}")

    def _fetch_reference(self) -> None:
        tag = self.tag_var.get().strip() or "master"
        self.reference_status.configure(text=f"正在获取 {tag} 的参考文件…",
                                        foreground=theme.TEXT_MUTED)

        def work(_task: Any) -> Path:
            return sources.fetch_reference_conf(tag)

        def done(path: Path) -> None:
            settings.set("reference_conf", str(path))
            self.reference_var.set(str(path))
            self.reference_status.configure(text=f"已保存到 {path}", foreground=theme.OK)
            self._apply_reference_change(f"参考文件已更新：{path}")

        def failed(exc: Exception) -> None:
            self.reference_status.configure(text=f"获取失败：{exc}", foreground=theme.ERROR)

        self.app.runner.submit(f"reference-{tag}", work, on_done=done, on_error=failed)

    def _apply_reference_change(self, message: str) -> None:
        self.app.notify(message, "ok")
        config_tab = self.app.tab("config")
        if config_tab is not None:
            config_tab.reload_model()

    def _clear_caches(self) -> None:
        if not self.app.ask_yes_no("清空版本缓存", "将删除所有已下载并解压的 DXVK 版本，继续？"):
            return
        removed = 0
        for kind in ("dxvk", "gplasync"):
            try:
                for child in cache_dir(kind).iterdir():
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                        removed += 1
            except OSError as exc:
                log.warning("cache cleanup failed: %s", exc)
        for kind in ("dxvk", "gplasync"):
            tab = self.app.tab(kind)
            if tab is not None and hasattr(tab, "_render"):
                tab._render()
        self.app.notify(f"已删除 {removed} 个已下载版本", "ok")

    def _open_readme(self) -> None:
        from ..paths import bundle_dir

        readme = bundle_dir() / "README.md"
        if readme.is_file():
            try:
                if os.name == "nt":
                    os.startfile(str(readme))  # type: ignore[attr-defined]
                else:
                    open_in_file_manager(readme)
            except OSError:
                self.app.notify(f"请手动打开 {readme}", "warn")
        else:
            self.app.notify("未找到 README.md", "warn")
