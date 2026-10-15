"""Fill the English translations into assets/i18n/app_en.ts.

Runs after pyside6-lupdate. Every (source -> English) mapping is asserted, so
a renamed string in the UI shows up as a missing key instead of silently
staying Chinese. The GameListModel context is added manually because its
strings flow through _tr()/QCoreApplication.translate with a variable source,
which lupdate cannot see.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TS = Path(__file__).resolve().parent.parent / "assets" / "i18n" / "app_en.ts"

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

CONFIG_PAGE = {
    "默认配置": "Default configuration",
    "默认配置（所有游戏共用）": "Default configuration (shared by all games)",
    "已写入": "Written",
    "与磁盘文件不同": "Differs from the file on disk",
    "未写入": "Not written",
    "状态未知": "State unknown",
    "搜索选项…": "Search options…",
    "简单": "Simple",
    "进阶": "Advanced",
    "完全": "Full",
    "导入 dxvk.conf…": "Import dxvk.conf…",
    "共 %1 项，已选 %2": "%1 options in total, %2 selected",
    "作用对象": "Applies to",
    "预设": "Preset",
    "选择预设…": "Pick a preset…",
    "存为预设": "Save as preset",
    "清空": "Clear all",
    "重置为默认": "Reset to defaults",
    "分类": "Categories",
    "全部": "All",
    "还没有可用的配置选项。\n先到「版本库」下载任意一个 DXVK 版本（自带参考文件），或到「设置」手动指定一个 dxvk.conf。":
        "No config options available yet.\nDownload any DXVK version on the Versions page first (it bundles a reference file), or point to a dxvk.conf manually in Settings.",
    "GPLAsync 专有": "GPLAsync only",
    "dxvk.conf 预览": "dxvk.conf preview",
    "带注释": "Comments",
    "复制": "Copy",
    "应用并写入 %1": "Apply and write to %1",
    "写入游戏…": "Write to game…",
    "保存为文件…": "Save as file…",
    "和游戏 exe 放在同一目录即可生效；这里可以独立导出，不需要扫描游戏。":
        "Placed next to the game exe it takes effect; export it here on its own, no library scan needed.",
    "把 dxvk.conf 写入哪个游戏？": "Which game should this dxvk.conf be written to?",
    "写入前会把已有的 dxvk.conf 备份为 .bkp": "Any existing dxvk.conf is backed up as .bkp before writing",
    "关闭": "Close",
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
    "切换界面文字，重启应用后生效；选项说明的语言独立设置，互不影响。":
        "Switches the UI text; takes effect after a restart. The option-description language is set separately and is unaffected.",
    "数据目录": "Data folder",
    "已下载的版本放在这里；游戏目录只会出现 DXVK 的 DLL 和安装时生成的 .bkp 备份。":
        "Downloaded versions live here; a game folder only ever shows the DXVK DLLs and the .bkp backups created on install.",
    "打开数据目录": "Open data folder",
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
}

TABLES = {
    "Bridge": BRIDGE,
    "ConfigPage": CONFIG_PAGE,
    "FilterSheet": FILTER_SHEET,
    "GameDetailDialog": GAME_DETAIL,
    "GamesPage": GAMES_PAGE,
    "SettingsPage": SETTINGS_PAGE,
    "VersionsPage": VERSIONS_PAGE,
    "main": MAIN,
    "GameListModel": GAME_LIST_MODEL,
}


def main() -> int:
    tree = ET.parse(TS)
    root = tree.getroot()
    if root.get("language") is None:
        root.set("language", "en_US")

    contexts: dict[str, ET.Element] = {}
    for ctx in root.iter("context"):
        name_el = ctx.find("name")
        assert name_el is not None and name_el.text is not None
        contexts[name_el.text] = ctx

    # Add contexts that lupdate cannot see (variable translate() sources).
    for name in TABLES:
        if name not in contexts:
            ctx = ET.SubElement(root, "context")
            ET.SubElement(ctx, "name").text = name
            contexts[name] = ctx

    missing: list[str] = []
    filled = 0
    for name, table in TABLES.items():
        ctx = contexts[name]
        seen: set[str] = set()
        for msg in ctx.findall("message"):
            src_el = msg.find("source")
            assert src_el is not None
            source = src_el.text or ""
            seen.add(source)
            if source not in table:
                missing.append(f"[{name}] {source!r}")
                continue
            tr = msg.find("translation")
            if tr is None:
                tr = ET.SubElement(msg, "translation")
            tr.text = table[source]
            tr.attrib.pop("type", None)
            filled += 1
        for source, english in table.items():
            if source not in seen:
                msg = ET.SubElement(ctx, "message")
                ET.SubElement(msg, "source").text = source
                ET.SubElement(msg, "translation").text = english
                filled += 1

    tree.write(TS, encoding="utf-8", xml_declaration=True)
    print(f"filled {filled} translations; missing {len(missing)}")
    for line in missing:
        print("  MISS", line)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
