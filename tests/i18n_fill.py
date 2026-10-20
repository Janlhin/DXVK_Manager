"""Generate assets/i18n/app_en.ts from the source tree.

Why this script exists instead of ``pyside6-lupdate``:
  * Qt derives the translation context of a QML ``qsTr()`` from the *file
    name* of the QML file. Splitting ``ConfigPage.qml`` into nine components
    therefore renamed the context and silently invalidated every translation.
  * ``lupdate`` cannot see the Python side: it builds contexts from the class
    name (``ConfigService``, ``LibraryService`` ...) while the runtime pins
    every Python string to the context ``Bridge`` (see
    ``dxvk_toolkit/ui/bridge/base.py``).
  * ``lupdate`` merges into an existing catalogue and keeps vanished entries
    forever, so the stale file silently rots.

So the catalogue is generated here from first principles:
  * QML contexts  -> scanned from ``dxvk_toolkit/ui/qml/*.qml`` (context = file stem)
  * ``Bridge``     -> scanned from ``dxvk_toolkit/ui/bridge/*.py`` (``tr("...")``)
  * ``GameListModel`` -> scanned from ``dxvk_toolkit/ui/models.py`` (``_tr("...")``)
                      plus the runtime-only sources (platform labels, config
                      purposes) that are imported from the pure-stdlib core.

Every source string must have an English translation in the tables below; a
missing or stale entry is a hard error (exit code 1). That makes this script a
gate, not a helper: it runs in CI (pure standard library) and refuses to let a
renamed string stay Chinese.

Usage:
    python tests/i18n_fill.py           # rewrite assets/i18n/app_en.ts
    python tests/i18n_fill.py --check   # fail if the committed file is stale
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "assets" / "i18n" / "app_en.ts"
QML_DIR = ROOT / "dxvk_toolkit" / "ui" / "qml"
BRIDGE_DIR = ROOT / "dxvk_toolkit" / "ui" / "bridge"
MODELS_PY = ROOT / "dxvk_toolkit" / "ui" / "models.py"

# ---------------------------------------------------------------------------
# Translation tables.  One table per translation context.
# ---------------------------------------------------------------------------

BRIDGE = {
    "指纹识别失败": "Fingerprinting failed",
    "接管失败": "Adoption failed",
    "默认配置": "Default configuration",
    "正在扫描游戏库…": "Scanning the game library…",
    "发现 {} 款游戏": "Found {} games",
    "扫描游戏库失败": "Failed to scan the game library",
    "选择游戏目录（包含游戏 exe）": "Choose the game folder (containing the game exe)",
    "该目录已在列表中": "That folder is already in the list",
    "已添加 {}": "Added {}",
    "识别 Direct3D 版本失败": "Failed to detect the Direct3D version",
    "离线模式：本地还没有版本缓存": "Offline: no local version cache yet",
    "离线模式：使用本地版本缓存": "Offline: using the local version cache",
    "正在强制刷新版本列表…": "Force-refreshing the version list…",
    "已获取 {} 个版本": "Fetched {} versions",
    "获取版本列表失败": "Failed to fetch the version list",
    "找不到版本 {}": "Version {} not found",
    "{} 下载完成": "{} downloaded",
    "下载失败": "Download failed",
    "{} 不在本地，无需删除": "{} is not stored locally, nothing to delete",
    "已删除 {}": "Deleted {}",
    "删除失败": "Delete failed",
    "请先选择一款游戏": "Select a game first",
    "安装失败": "Install failed",
    "还原失败": "Restore failed",
    "已移除 {} 个文件": "Removed {} files",
    "移除失败": "Removal failed",
    "读取缓存统计失败": "Failed to read cache statistics",
    "已清理 {} 个缓存版本": "Cleared {} cached versions",
    "没有可清理的缓存版本": "No cache versions to clear",
    "清理缓存失败": "Cache cleanup failed",
    "没有失效的安装记录": "No stale install records",
    "已清理 {} 条失效的安装记录": "Removed {} stale install records",
    "清理记录失败": "Record cleanup failed",
    "正在载入 dxvk.conf 选项…": "Loading dxvk.conf options…",
    "未找到参考文件": "reference file not found",
    "共 {} 个选项（{}）": "{} options ({})",
    "载入配置选项失败": "Failed to load the config options",
    "还没有载入参考文件": "No reference file loaded yet",
    "已还原：{}": "Restored: {}",
    "导入 dxvk.conf": "Import dxvk.conf",
    "读取失败：{}": "Failed to read: {}",
    "已从 {} 导入 {} 个选项": "Imported {} options from {}",
    "，另有 {} 个选项不在参考文件里（已忽略）":
        "; another {} options are not in the reference file (ignored)",
    "找不到这款游戏，请先扫描游戏库": "Game not found; scan the game library first",
    "写入失败：{}": "Failed to write: {}",
    "已写入 {}": "Written to {}",
    "导出 dxvk.conf": "Export dxvk.conf",
    "已导出到 {}": "Exported to {}",
    "已保存预设「{}」": "Saved preset \"{}\"",
    "内置预设不能覆盖，请换一个名字":
        "Built-in presets cannot be overwritten - please pick another name",
    "操作失败": "Operation failed",
    "找到本地代理 {}，已切换为自定义代理":
        "Found a local proxy at {}; switched to the custom proxy",
    "没有在常见端口上发现本地代理": "No local proxy found on the usual ports",
    "自动（优先官方，失败走镜像）": "Auto (official first, mirrors on failure)",
    "仅官方 GitHub": "Official GitHub only",
    "只用镜像 {}": "Mirror only: {}",
    "下载源：{}": "Download source: {}",
    "DXVK 官方仓库": "DXVK official repository",
    "DXVK Wiki（文档）": "DXVK Wiki (documentation)",
    "DXVK 发布页": "DXVK releases page",
    "dxvk.conf 原文": "Original dxvk.conf",
    "doitsujin 及贡献者": "doitsujin and contributors",
    "本工具下载并安装它的发布版本；选项说明来自其 dxvk.conf。":
        "This tool downloads and installs its releases; the option descriptions come from its dxvk.conf.",
    "Ph42oN 维护": "maintained by Ph42oN",
    "随项目": "follows the project",
    "带 async 补丁的 DXVK 分支，作为可选下载来源。":
        "DXVK fork carrying the async patch, offered as an optional download source.",
    "功能蓝本：Steam 库扫描、版本管理、DLL 备份与还原。本项目为其 Python 重写。":
        "Functional blueprint: Steam library scan, version management, DLL backup and restore. This project is a Python rewrite of it.",
    "功能蓝本：从 dxvk.conf 生成配置界面。本项目独立实现，未复制其代码。":
        "Functional blueprint: a configuration UI generated from dxvk.conf. Implemented independently; no code was copied.",
    "界面框架（QML / Qt Quick）。": "UI framework (QML / Qt Quick).",
    "Python Imaging Library 社区": "Python Imaging Library community",
    "旧版封面缩略图使用；QML 版已能自行缩放，仅在命令行路径仍会用到。":
        "Used by the legacy cover thumbnails; the QML UI scales images itself, only the command-line path still uses it.",
    "运行环境。": "Runtime.",
    "数据与网络来源": "Data and network sources",
    "各自条款": "their respective terms",
    "封面图、发布版本列表、版本列表兜底、可选的兼容性信息。":
        "Cover art, release listings, version list fallback, optional compatibility info.",
    "已复制到剪贴板": "Copied to the clipboard",
    "正在补齐中文名 {}/{}": "Fetching Chinese names {}/{}",
    "已补齐 {} 个中文名": "Fetched {} Chinese names",
    "已识别 {} 款游戏的 Direct3D 版本": "Detected the Direct3D version of {} games",
}

# -- Config page, split per QML component -------------------------------
# Qt uses the QML file name as the context, so each component owns its table.

CONFIG_PAGE = {
    "默认配置": "Default configuration",
    "默认配置（所有游戏共用）": "Default configuration (shared by all games)",
    "已写入": "Written",
    "与磁盘文件不同": "Differs from the file on disk",
    "未写入": "Not written",
    "状态未知": "State unknown",
}

CONFIG_TOOLBAR = {
    "搜索选项…": "Search options…",
    "简单": "Simple",
    "进阶": "Advanced",
    "完全": "Full",
    "导入 dxvk.conf…": "Import dxvk.conf…",
    "共 %1 项，已选 %2": "%1 options in total, %2 selected",
}

CONFIG_RAIL = {
    "分类": "Categories",
    "全部": "All",
}

CONFIG_CONTEXT_BAR = {
    "作用对象": "Applies to",
    "预设": "Preset",
    "选择预设…": "Pick a preset…",
    "存为预设": "Save as preset",
    "清空": "Clear all",
    "重置为默认": "Reset to defaults",
}

CONFIG_OPTION_LIST = {
    "还没有可用的配置选项。\n先到「版本库」下载任意一个 DXVK 版本（自带参考文件），或到「设置」手动指定一个 dxvk.conf。":
        "No config options available yet.\nDownload any DXVK version on the Versions page first (it bundles a reference file), or point to a dxvk.conf manually in Settings.",
    "GPLAsync 专有": "GPLAsync only",
}

CONFIG_PREVIEW_PANE = {
    "dxvk.conf 预览": "dxvk.conf preview",
    "带注释": "Comments",
    "复制": "Copy",
    "应用并写入 %1": "Apply and write to %1",
    "写入游戏…": "Write to game…",
    "保存为文件…": "Save as file…",
    "和游戏 exe 放在同一目录即可生效；这里可以独立导出，不需要扫描游戏。":
        "Placed next to the game exe it takes effect; export it here on its own, no library scan needed.",
}

CONFIG_DOC_CARD = {
    "说明": "Summary",
    "示例": "Example",
    "DXVK 原文": "Upstream text",
}

CONFIG_GAME_PICKER = {
    "把 dxvk.conf 写入哪个游戏？": "Which game should this dxvk.conf be written to?",
    "写入前会把已有的 dxvk.conf 备份为 .bkp": "Any existing dxvk.conf is backed up as .bkp before writing",
    "关闭": "Close",
}

CONFIG_PRESET_DIALOG = {
    "保存为预设": "Save as preset",
    "把当前勾选的所有选项保存为自定义预设，之后可在任意游戏上一键套用。":
        "Saves every currently selected option as a custom preset that can be applied to any game in one click.",
    "预设名称，例如：赛博朋克专用": "Preset name, e.g. Cyberpunk 2077",
    "「性能优先」「兼容优先」「纯净」为内置预设，不可覆盖。":
        "\"Performance\", \"Compatibility\" and \"Clean\" are built-in presets and cannot be overwritten.",
    "保存": "Save",
    "取消": "Cancel",
}

FILTER_SHEET = {
    "筛选与视图": "Filters and view",
    "状态": "Status",
    "全部 %1": "All %1",
    "已装 DXVK %1": "DXVK installed %1",
    "未安装 %1": "Not installed %1",
    "平台": "Platform",
    "视图": "View",
    "卡片": "Cards",
    "列表": "List",
    "排序": "Sort by",
    "名称": "Name",
    "架构": "Arch",
    "已装优先": "Installed first",
    "方向": "Direction",
    "↑ 升序": "↑ Ascending",
    "↓ 降序": "↓ Descending",
    "重置": "Reset",
    "关闭": "Close",
}

GAME_DETAIL = {
    "官方 DXVK": "Official DXVK",
    "安装路径": "Install path",
    "打开目录": "Open folder",
    "Direct3D 识别中…": "Detecting Direct3D…",
    "Direct3D 未知": "Direct3D unknown",
    "DXVK 来源": "DXVK source",
    "版本": "Version",
    " · 下载中…": " · downloading…",
    " · 已下载": " · downloaded",
    " · 未下载": " · not downloaded",
    "（下载中…）": " (downloading…)",
    "（没有可用版本）": "(no versions available)",
    "下载中…": "Downloading…",
    "已下载": "Downloaded",
    "未下载 · 选后自动下载": "Not downloaded · picked versions download automatically",
    "正在下载 %1 …完成后即可「应用 DXVK」，请稍候。":
        "Downloading %1 … you can \"Apply DXVK\" once it finishes; please wait.",
    "没有可用版本：离线且本地无缓存。联网后可到「版本库」点「强制刷新」。":
        "No versions available: offline with no local cache. Go online and press \"Force refresh\" on the Versions page.",
    "共 %1 个可下载版本，已下载 %2 个。选择未下载的版本会自动下载；应用时会自动备份原有 DLL（.bkp）。":
        "%1 downloadable versions, %2 downloaded. Picking a version that is not downloaded fetches it automatically; applying backs up the original DLLs (.bkp).",
    "应用 DXVK": "Apply DXVK",
    "DXVK 配置": "DXVK config",
    "还原原始 DLL": "Restore original DLLs",
    "移除 DXVK": "Remove DXVK",
    "关闭": "Close",
    "已装 %1（%2）· 哈希与官方缓存一致，未经修改":
        "Installed %1 (%2) · hashes match the official cache, unmodified",
    "已装 DXVK v%1（%2）· 与本地缓存不符：魔改或非官方构建，也可能是本地未下载该版本":
        "Installed DXVK v%1 (%2) · differs from the local cache: modified or unofficial build, or simply a version not downloaded here",
    "已装 DXVK（%1）· 二进制未带版本标记，无法核对来源":
        "Installed DXVK (%1) · the binaries carry no version banner, source cannot be verified",
    "接管此安装": "Adopt this installation",
    "接管并补还原点": "Adopt + build restore points",
    "接管后此 DXVK 归本工具管理：显示版本、可直接升级；还原点从 Windows 系统目录补建（并非游戏原始文件）。":
        "After adoption this DXVK is managed here: its version is shown and upgrades work directly; restore points are built from the Windows system directories (they are not the game's original files).",
    "移除未接管的 DXVK？": "Remove the unmanaged DXVK?",
    "这套 DXVK 不是本工具安装的，移除后无法通过本工具还原。":
        "This DXVK was not installed by this tool; once removed it cannot be restored here.",
    "即将删除：DXVK v%1。": "About to delete: DXVK v%1.",
    "取消": "Cancel",
    "仍要移除": "Remove anyway",
    "移除 DXVK？": "Remove DXVK?",
    "即将从游戏目录删除 DXVK v%1 并清除接管记录。":
        "DXVK v%1 will be deleted from the game folder and the takeover record cleared.",
    "即将从游戏目录删除 DXVK 并清除接管记录。":
        "DXVK will be deleted from the game folder and the takeover record cleared.",
    "同时清理 dxvk.conf、DXVK 日志与着色器缓存":
        "Also remove dxvk.conf, the DXVK logs and the shader cache",
}

GAMES_PAGE = {
    "已装 DXVK": "DXVK installed",
    "未安装": "Not installed",
    "筛选": "Filters",
    "筛选：%1": "Filters: %1",
    "搜索游戏…": "Search games…",
    "＋ 添加文件夹": "＋ Add folder",
    "扫描": "Scan",
    "识别中…": "Detecting…",
    "Direct3D 未知": "Direct3D unknown",
    "名称": "Name",
    "平台": "Platform",
    "架构": "Arch",
    "详情": "Details",
    "打开目录": "Open folder",
    "还没有游戏": "No games yet",
    "点「扫描」读取 Steam 库（含所有库文件夹），或「＋ 添加文件夹」指定任意游戏目录。":
        "Press \"Scan\" to read the Steam library (including every library folder), or use \"＋ Add folder\" to pick any game directory.",
    "开始扫描": "Start scan",
}

SETTINGS_PAGE = {
    "离线模式": "Offline mode",
    "打开后程序不发起任何网络请求：版本列表与封面只使用本地已有内容，下载会直接提示离线模式已开启。":
        "When on, the app makes no network requests: version lists and covers come from local content only, and downloads report that offline mode is on.",
    "网络与下载源": "Network and download source",
    "代理": "Proxy",
    "自动": "Auto",
    "直连": "Direct",
    "自定义": "Custom",
    "探测本地代理": "Detect local proxy",
    "下载源": "Download source",
    "官方源被墙时自动改用镜像": "Falls back to mirrors automatically when the official source is unreachable",
    "测试连接": "Test connection",
    "测试中…": "Testing…",
    "点「测试连接」会真实拉取一次版本列表": "\"Test connection\" actually fetches the version list once",
    "导出的 dxvk.conf": "Exported dxvk.conf",
    "开启后每个选项上方会写入中文说明（与原版工具一致）；关闭则只输出选项本身。预览与导出使用同一份内容。":
        "When on, each option gets a comment above it (like the original tool); when off, only the options are written. Preview and export share the same content.",
    "界面语言": "Interface language",
    "简体中文": "简体中文",
    "切换界面文字立即生效，无需重启；选项说明的语言独立设置，互不影响。":
        "Switches the UI text immediately; no restart needed. The option-description language is set separately and is unaffected.",
    "数据目录": "Data folder",
    "已下载的版本放在这里；游戏目录只会出现 DXVK 的 DLL 和安装时生成的 .bkp 备份。":
        "Downloaded versions live here; a game folder only ever shows the DXVK DLLs and the .bkp backups created on install.",
    "打开数据目录": "Open data folder",
    "存储与清理": "Storage & cleanup",
    "dxvk 缓存 %1（%2 个版本） · gplasync 缓存 %3（%4 个版本） · 失效安装记录 %5 条":
        "dxvk cache %1 (%2 versions) · gplasync cache %3 (%4 versions) · %5 stale install records",
    "清空缓存会保留正在被游戏使用的版本；游戏目录里的着色器缓存等伴生文件在游戏详情的「移除 DXVK」里清理。":
        "A blanket wipe keeps the versions some game runs on; shader caches and other companion files in a game folder are cleaned via \"Remove DXVK\" in the game details.",
    "清空 dxvk 缓存": "Clear dxvk cache",
    "清空 gplasync 缓存": "Clear gplasync cache",
    "清理失效安装记录": "Prune stale install records",
    "清空 dxvk 缓存？": "Clear the dxvk cache?",
    "清空 gplasync 缓存？": "Clear the gplasync cache?",
    "没有可清理的版本——其余版本正被游戏使用，会保留。":
        "Nothing to clear - the remaining versions are in use by games and will be kept.",
    "将删除 %1 个版本，共 %2。正在被游戏使用的版本会保留。":
        "%1 versions (%2) will be deleted. Versions in use by games are kept.",
    "取消": "Cancel",
    "清空": "Clear",
    "官方资源": "Official resources",
    "鸣谢": "Credits",
    "查看完整第三方声明": "View full third-party notices",
    "第三方声明": "Third-Party Notices",
    "未找到第三方声明文件。": "The third-party notices file was not found.",
    "关于": "About",
    "DXVK Version Manager · Python edition v%1\n界面：PySide6 + QML（Qt Quick）；核心逻辑为与界面无关的纯 Python 标准库实现。中文选项说明由本项目翻译，英文原文来自 DXVK 的 dxvk.conf。":
        "DXVK Version Manager · Python edition v%1\nUI: PySide6 + QML (Qt Quick); the core logic is a pure Python standard-library implementation independent of the UI. The Chinese option descriptions are translated by this project; the English originals come from DXVK's dxvk.conf.",
}

VERSIONS_PAGE = {
    "官方 DXVK": "Official DXVK",
    "已下载 %1 个": "%1 downloaded",
    "还没有下载版本": "No versions downloaded yet",
    "获取中…": "Fetching…",
    "强制刷新": "Force refresh",
    "（官方未提供说明）": "(no notes provided upstream)",
    "已下载": "Downloaded",
    "正在获取版本列表…": "Fetching the version list…",
    "还没有版本列表": "No version list yet",
    "首次获取需要联网；之后会立即显示本地缓存。":
        "The first fetch needs a connection; afterwards the local cache shows up immediately.",
    "点「强制刷新」从官方源获取；已下载的版本在本地，离线也能用。":
        "Press \"Force refresh\" to fetch from the official source; downloaded versions are local and work offline.",
    "点一个版本卡片，这里显示它的完整更新说明与操作":
        "Pick a version card to see its full release notes and actions here",
    "   ·   已下载到本地": "   ·   downloaded locally",
    "重新下载": "Re-download",
    "下载": "Download",
    "复制链接": "Copy link",
    "Release 页": "Release page",
    "删除本地": "Delete local copy",
    "直接应用到游戏": "Apply directly to a game",
    "选择游戏…": "Pick a game…",
    "应用": "Apply",
    "下载中…  ": "Downloading…  ",
    "删除本地版本": "Delete the local copy",
    "把 %1 从本地缓存删除？\n\n已安装到游戏的 DLL 不受影响；之后想用可随时重新下载。":
        "Delete %1 from the local cache?\n\nDLLs already installed into games are unaffected; you can always download it again.",
    "删除": "Delete",
    "取消": "Cancel",
}

MAIN = {
    "就绪": "Ready",
    "游戏库": "Games",
    "扫描并管理游戏": "Scan and manage games",
    "版本库": "Versions",
    "下载 DXVK 版本": "Download DXVK versions",
    "配置": "Config",
    "生成 dxvk.conf": "Generate dxvk.conf",
    "设置": "Settings",
    "离线模式与数据目录": "Offline mode and data folder",
    "处理中…": "Working…",
}

GAME_LIST_MODEL = {
    "目录缺失": "Folder missing",
    "已装 DXVK": "DXVK installed",
    "已装·未接管": "Installed · unmanaged",
    "可还原": "Restorable",
    "未安装": "Not installed",
    "未知": "Unknown",
    "帧率与同步": "Framerate and sync",
    "画面与输出": "Display and output",
    "性能优化": "Performance",
    "兼容性": "Compatibility",
    "显示与诊断": "Rendering and diagnostics",
    "其他": "Other",
    # Platform labels from steam.PLATFORM_LABELS, routed through _tr() when the
    # row data and the filter chips are built. Most are identical in English;
    # they are registered so a renamed label cannot silently stay Chinese.
    "Steam": "Steam",
    "Epic": "Epic",
    "GOG": "GOG",
    "Ubisoft": "Ubisoft",
    "Battle.net": "Battle.net",
    "Riot": "Riot",
    "WeGame": "WeGame",
    "米哈游": "miHoYo",
    "EA": "EA",
    "itch.io": "itch.io",
    "手动添加": "Manual",
    "全部": "All",
}

TABLES: dict[str, dict[str, str]] = {
    "Bridge": BRIDGE,
    "ConfigContextBar": CONFIG_CONTEXT_BAR,
    "ConfigDocCard": CONFIG_DOC_CARD,
    "ConfigGamePicker": CONFIG_GAME_PICKER,
    "ConfigOptionList": CONFIG_OPTION_LIST,
    "ConfigPage": CONFIG_PAGE,
    "ConfigPresetDialog": CONFIG_PRESET_DIALOG,
    "ConfigPreviewPane": CONFIG_PREVIEW_PANE,
    "ConfigRail": CONFIG_RAIL,
    "ConfigToolbar": CONFIG_TOOLBAR,
    "FilterSheet": FILTER_SHEET,
    "GameDetailDialog": GAME_DETAIL,
    "GameListModel": GAME_LIST_MODEL,
    "GamesPage": GAMES_PAGE,
    "SettingsPage": SETTINGS_PAGE,
    "VersionsPage": VERSIONS_PAGE,
    "main": MAIN,
}

# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------

_QSTR_RE = re.compile(r'qsTr\(\s*"((?:[^"\\]|\\.)*)"')
_TR_RE = re.compile(r'(?<![A-Za-z_])tr\(\s*"((?:[^"\\]|\\.)*)"')
_TR_SQ_RE = re.compile(r"(?<![A-Za-z_])tr\(\s*'((?:[^'\\]|\\.)*)'")
_MODEL_TR_RE = re.compile(r'_tr\(\s*"((?:[^"\\]|\\.)*)"')
_MODEL_TR_SQ_RE = re.compile(r"_tr\(\s*'((?:[^'\\]|\\.)*)'")

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}


def _unescape(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _scan_qml() -> dict[str, dict[str, list[str]]]:
    """context (QML file stem) -> source -> ["<file>:<line>", ...]."""
    found: dict[str, dict[str, list[str]]] = {}
    for path in sorted(QML_DIR.glob("*.qml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        bucket: dict[str, list[str]] = {}
        for lineno, line in enumerate(lines, start=1):
            for raw in _QSTR_RE.findall(line):
                bucket.setdefault(_unescape(raw), []).append(f"{_rel(path)}:{lineno}")
        # A QML file without any qsTr() has no translation context at all.
        if bucket:
            found[path.stem] = bucket
    return found


def _scan_python_tr() -> dict[str, dict[str, list[str]]]:
    """context ``Bridge`` -> source -> locations."""
    found: dict[str, dict[str, list[str]]] = {"Bridge": {}}
    for path in sorted(BRIDGE_DIR.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            raws = list(_TR_RE.findall(line)) + list(_TR_SQ_RE.findall(line))
            for raw in raws:
                found["Bridge"].setdefault(_unescape(raw), []).append(
                    f"{_rel(path)}:{lineno}")
    return found


def _runtime_only_sources() -> dict[str, set[str]]:
    """Sources that exist only at runtime (dynamic lookup keys)."""
    sys.path.insert(0, str(ROOT))
    from dxvk_toolkit.confkit.curate import PURPOSE_ORDER  # noqa: PLC0415
    from dxvk_toolkit.steam import PLATFORM_LABELS  # noqa: PLC0415

    return {
        "GameListModel": set(PURPOSE_ORDER) | set(PLATFORM_LABELS.values()),
    }


def _scan_model_tr() -> dict[str, dict[str, list[str]]]:
    lines = MODELS_PY.read_text(encoding="utf-8").splitlines()
    bucket: dict[str, list[str]] = {}
    for lineno, line in enumerate(lines, start=1):
        raws = list(_MODEL_TR_RE.findall(line)) + list(_MODEL_TR_SQ_RE.findall(line))
        for raw in raws:
            bucket.setdefault(_unescape(raw), []).append(f"{_rel(MODELS_PY)}:{lineno}")
    return {"GameListModel": bucket}


def collect_sources() -> dict[str, dict[str, list[str]]]:
    sources: dict[str, dict[str, list[str]]] = {}
    for context, bucket in _scan_qml().items():
        sources.setdefault(context, {}).update(bucket)
    for context, bucket in _scan_python_tr().items():
        sources.setdefault(context, {}).update(bucket)
    for context, bucket in _scan_model_tr().items():
        sources.setdefault(context, {}).update(bucket)
    for context, extra in _runtime_only_sources().items():
        for source in extra:
            sources.setdefault(context, {}).setdefault(source, [])
    return sources


# ---------------------------------------------------------------------------
# Catalogue generation
# ---------------------------------------------------------------------------


def _message(parent: ET.Element, source: str, english: str,
             locations: list[str]) -> None:
    msg = ET.SubElement(parent, "message")
    for loc in locations:
        filename, _, line = loc.rpartition(":")
        ET.SubElement(msg, "location", {"filename": filename, "line": line})
    ET.SubElement(msg, "source").text = source
    ET.SubElement(msg, "translation").text = english


def build_catalogue(sources: dict[str, dict[str, list[str]]]) -> tuple[str, list[str]]:
    """Return (xml text, problems)."""
    problems: list[str] = []
    root = ET.Element("TS", {"version": "2.1", "language": "en_US"})
    for context in sorted(sources):
        table = TABLES.get(context)
        if table is None:
            problems.append(f"[{context}] no translation table defined")
            continue
        bucket = sources[context]
        for source in sorted(bucket):
            if source not in table:
                problems.append(f"[{context}] {source!r} has no English translation")
        for source in sorted(table):
            if source not in bucket:
                problems.append(f"[{context}] {source!r} is stale (not used any more)")
        ctx = ET.SubElement(root, "context")
        ET.SubElement(ctx, "name").text = context
        for source in sorted(bucket):
            english = table.get(source)
            if english is None:
                continue
            _message(ctx, source, english, bucket[source])
    ET.indent(root, space="    ")
    xml = ET.tostring(root, encoding="unicode")
    return f"<?xml version='1.0' encoding='utf-8'?>\n{xml}\n", problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail instead of writing when the catalogue is stale")
    args = parser.parse_args()

    sources = collect_sources()
    xml, problems = build_catalogue(sources)
    if problems:
        print(f"i18n catalogue has {len(problems)} problem(s):", file=sys.stderr)
        for line in problems:
            print("  ", line, file=sys.stderr)
        return 1

    total = sum(len(v) for v in sources.values())
    if args.check:
        current = TS.read_text(encoding="utf-8") if TS.is_file() else ""
        if current != xml:
            print(f"{TS} is out of date - rerun 'python tests/i18n_fill.py'",
                  file=sys.stderr)
            return 1
        print(f"i18n catalogue up to date ({total} messages, {len(sources)} contexts)")
        return 0

    TS.parent.mkdir(parents=True, exist_ok=True)
    TS.write_text(xml, encoding="utf-8")
    print(f"wrote {TS} ({total} messages, {len(sources)} contexts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
