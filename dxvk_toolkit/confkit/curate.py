"""Which options this tool treats as basic, advanced or legacy.

This is curation, not parsing: a host that disagrees can ignore this module and
supply its own key sets."""

from __future__ import annotations



BASIC_KEYS = (
    # frame pacing and sync
    "maxFrameRate",
    "syncInterval",
    "presentInterval",
    "maxFrameLatency",
    "tearFree",
    # picture and output
    "enableHDR",
    "hdr",
    "samplerAnisotropy",
    "samplerLodBias",
    # performance switches people actually flip
    "numCompilerThreads",
    "enableGraphicsPipelineLibrary",
    "enableAsync",
    "maxFeatureLevel",
    # multi-GPU and compatibility
    "deviceFilter",
    "deferSurfaceCreation",
    # on-screen display
    "hud",
)


LEGACY_KEYS = (
    "supportX4R4G4B4",
    "disableA8RT",
    "placeP8InScratch",
    "forceLegacyBuffers",
    "shadowPerspectiveDivide",
    "scaleDref",
    "floatEmulation",
    "lowerSinCos",
    "memoryTrackTest",
    "useD32forD24",
    "supportDFFormats",
    "disableDirectImageMapping",
    "reproducibleCommandStream",
    "enableDebugUtils",
    "countLosableResources",
    "deviceLossOnFocusLoss",
    "maxAvailableMemory",
    "forceVsDecl",
)


GPLASYNC_ONLY: dict[str, dict[str, str]] = {
    "enableAsync": {
        "label": "异步着色器编译",
        "summary": "GPLAsync 专有：在后台线程编译着色器，减少首次进入新场景的卡顿；"
                   "代价是可能出现贴图短暂弹出。官方 DXVK 无此选项。",
        "example": "True",
        "section": "dxvk",
        "tier": "simple",
    },
    "gplAsyncCache": {
        "label": "状态缓存配合 GPL",
        "summary": "GPLAsync 专有：让状态缓存与图形管线库配合工作；"
                   "该分支 v2.7-1 起已移除，仅旧版本需要。",
        "example": "True",
        "section": "dxvk",
        "tier": "advanced",
    },
}


def build_of(key: str) -> str:
    """Which build an option belongs to: "gplasync" or "both"."""
    return "gplasync" if key in GPLASYNC_ONLY else "both"


MODES = ("simple", "advanced", "full")


PURPOSE_ORDER = ("帧率与同步", "画面与输出", "性能优化", "兼容性", "显示与诊断", "其他")


PURPOSE: dict[str, str] = {
    "maxFrameRate": "帧率与同步",
    "syncInterval": "帧率与同步",
    "presentInterval": "帧率与同步",
    "maxFrameLatency": "帧率与同步",
    "tearFree": "帧率与同步",
    "latencySleep": "帧率与同步",
    "latencyTolerance": "帧率与同步",
    "enableHDR": "画面与输出",
    "samplerAnisotropy": "画面与输出",
    "samplerLodBias": "画面与输出",
    "clampNegativeLodBias": "画面与输出",
    "numCompilerThreads": "性能优化",
    "enableGraphicsPipelineLibrary": "性能优化",
    "enableMemoryDefrag": "性能优化",
    "relaxedBarriers": "性能优化",
    "relaxedGraphicsBarriers": "性能优化",
    "maxFeatureLevel": "兼容性",
    "deferSurfaceCreation": "兼容性",
    "deviceFilter": "兼容性",
    "hideNvidiaGpu": "兼容性",
    "hideAmdGpu": "兼容性",
    "hideIntelGpu": "兼容性",
    "forceAspectRatio": "兼容性",
    "forceRefreshRate": "兼容性",
    "hud": "显示与诊断",
    "enableDebugUtils": "显示与诊断",
    "dpiAware": "显示与诊断",
}


def purpose_of(key: str) -> str:
    return PURPOSE.get(key, "其他")


def tier_of(key: str, section: str = "") -> str:
    """Lowest mode in which an option is listed."""
    if section == "d3d8" or key in LEGACY_KEYS:
        return "full"
    if key in BASIC_KEYS:
        return "simple"
    return "advanced"


_FORK_CONF = """
[dxvk]
# GPLAsync 专有选项（官方 dxvk.conf 中不存在）
# dxvk.enableAsync = True
# dxvk.gplAsyncCache = True
"""
