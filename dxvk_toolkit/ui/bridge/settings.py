"""Settings and shell domain: preferences, proxies, links and the app shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ... import APP_VERSION, sources
from ...paths import bundle_dir, data_root, settings
from ...util import log, open_in_file_manager
from .base import BridgeService


class SettingsService(BridgeService):
    """User preferences and the handful of OS-level helpers the UI needs."""

    # -- proxy -------------------------------------------------------------
    def probe_local_proxy(self) -> str:
        """Look for a proxy listening on the usual local ports.

        Most proxy clients in China (Clash, v2ray, sing-box) sit on one of a
        handful of ports; finding it saves the user from typing it in.
        """
        import socket

        for port in (7897, 7890, 7891, 10809, 10808, 1080, 2080, 8889, 8080):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                    pass
            except OSError:
                continue
            address = f"http://127.0.0.1:{port}"
            settings.set("proxy_url", address)
            settings.set("proxy_mode", "custom")
            self._status(self.tr("找到本地代理 {}，已切换为自定义代理").format(address), "ok")
            return address
        self._status(self.tr("没有在常见端口上发现本地代理"), "warn")
        return ""

    # -- download source ---------------------------------------------------
    def download_sources(self) -> Any:
        """Choices for the release download source."""
        options = [
            {"value": "auto", "label": self.tr("自动（优先官方，失败走镜像）")},
            {"value": "official", "label": self.tr("仅官方 GitHub")},
        ]
        for prefix in sources.MIRROR_PREFIXES:
            options.append({"value": f"mirror:{prefix.rstrip('/')}", "label": self.tr("只用镜像 {}").format(prefix.rstrip('/'))})
        return options

    def set_download_source(self, value: str) -> None:
        settings.set("download_source", value or "auto")
        label = next(
            (item["label"] for item in self.download_sources() if item["value"] == value),
            value,
        )
        self._status(self.tr("下载源：{}").format(label), "ok")

    def current_download_source(self) -> str:
        return str(settings.get("download_source") or "auto")

    # -- key/value settings -------------------------------------------------
    def get_setting(self, key: str) -> Any:
        return settings.get(key)

    def set_setting(self, key: str, value: Any) -> None:
        settings.set(key, value)
        if key == "ui_lang":
            self._apply_language(str(value))

    def _apply_language(self, lang: str) -> None:
        """Swap the live translator and refresh already-built UI strings (§28).

        QML qsTr() bindings re-evaluate on their own; the Python-resolved model
        strings and the config target name are refreshed here.
        """
        from .. import app_qml

        app_qml.set_language(lang)
        self._host.model.retranslate()
        self._host._config_service.refresh_target_name()
        self._host.languageChanged.emit()

    # -- app shell ----------------------------------------------------------
    def data_root(self) -> str:
        return str(data_root())

    def app_version(self) -> str:
        return APP_VERSION

    def open_data_folder(self) -> None:
        open_in_file_manager(data_root())

    def open_url(self, url: str) -> None:
        """Open a link in the default browser (only ever from a user click)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))
        log.info("opened link: %s", url)

    def official_links(self) -> Any:
        return [
            {"label": self.tr("DXVK 官方仓库"), "url": "https://github.com/doitsujin/dxvk"},
            {"label": self.tr("DXVK Wiki（文档）"), "url": "https://github.com/doitsujin/dxvk/wiki"},
            {"label": self.tr("DXVK 发布页"), "url": "https://github.com/doitsujin/dxvk/releases"},
            {"label": self.tr("dxvk.conf 原文"), "url": "https://github.com/doitsujin/dxvk/blob/master/dxvk.conf"},
            {"label": "DXVK-gplasync", "url": "https://gitlab.com/Ph42oN/dxvk-gplasync"},
            {"label": "PCGamingWiki", "url": "https://www.pcgamingwiki.com/"},
        ]

    def credits(self) -> Any:
        """Acknowledgements, with the licence each project is used under."""
        return [
            {
                "name": "DXVK",
                "author": self.tr("doitsujin 及贡献者"),
                "license": "zlib",
                "role": self.tr("本工具下载并安装它的发布版本；选项说明来自其 dxvk.conf。"),
                "url": "https://github.com/doitsujin/dxvk",
            },
            {
                "name": "DXVK-gplasync",
                "author": self.tr("Ph42oN 维护"),
                "license": self.tr("随项目"),
                "role": self.tr("带 async 补丁的 DXVK 分支，作为可选下载来源。"),
                "url": "https://gitlab.com/Ph42oN/dxvk-gplasync",
            },
            {
                "name": "dxvk-version-mananger",
                "author": "artmakh",
                "license": "MIT",
                "role": self.tr("功能蓝本：Steam 库扫描、版本管理、DLL 备份与还原。本项目为其 Python 重写。"),
                "url": "https://github.com/artmakh/dxvk-version-mananger",
            },
            {
                "name": "DXVK-Configurator",
                "author": "CamoMano",
                "license": "GPL-3.0",
                "role": self.tr("功能蓝本：从 dxvk.conf 生成配置界面。本项目独立实现，未复制其代码。"),
                "url": "https://github.com/CamoMano/DXVK-Configurator",
            },
            {
                "name": "Qt for Python (PySide6)",
                "author": "Qt Company",
                "license": "LGPL-3.0",
                "role": self.tr("界面框架（QML / Qt Quick）。"),
                "url": "https://www.qt.io/qt-for-python",
            },
            {
                "name": "Pillow",
                "author": self.tr("Python Imaging Library 社区"),
                "license": "MIT-CMU",
                "role": self.tr("旧版封面缩略图使用；QML 版已能自行缩放，仅在命令行路径仍会用到。"),
                "url": "https://python-pillow.org/",
            },
            {
                "name": "Python",
                "author": "Python Software Foundation",
                "license": "PSF",
                "role": self.tr("运行环境。"),
                "url": "https://www.python.org/",
            },
            {
                "name": self.tr("数据与网络来源"),
                "author": "Steam CDN / GitHub / GitLab / jsDelivr / PCGamingWiki",
                "license": self.tr("各自条款"),
                "role": self.tr("封面图、发布版本列表、版本列表兜底、可选的兼容性信息。"),
                "url": "https://github.com/doitsujin/dxvk",
            },
        ]

    def notices_text(self) -> str:
        """Full text of THIRD_PARTY_NOTICES.md for the in-app viewer."""
        path = bundle_dir() / "THIRD_PARTY_NOTICES.md"
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log.warning("Third-party notices file missing: %s", path)
            return ""

    def open_folder(self, path: str) -> None:
        target = Path(path)
        open_in_file_manager(target if target.exists() else target.parent)

    def copy_text(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self._status(self.tr("已复制到剪贴板"), "ok")
