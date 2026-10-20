"""Qt list models exposed to QML.

The models are plain views over data the core already produces; nothing here
talks to the network or the disk on its own.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QCoreApplication,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)

from .. import covers, installer, steam
from ..paths import settings


class GameListModel(QAbstractListModel):
    """The game library, one row per game folder."""

    # rowCount() carries no change notification, so QML cannot bind to it;
    # this property does, which is what the empty-state visibility needs.
    countChanged = Signal()

    @Property(int, notify=countChanged)
    def count(self) -> int:  # noqa: A003 - name is dictated by QML usage
        return len(self._rows)

    KeyRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    PlatformRole = Qt.UserRole + 3
    PlatformLabelRole = Qt.UserRole + 4
    Direct3DRole = Qt.UserRole + 5
    ArchRole = Qt.UserRole + 6
    StatusRole = Qt.UserRole + 7
    StatusKindRole = Qt.UserRole + 8
    CoverRole = Qt.UserRole + 9
    PathRole = Qt.UserRole + 10
    AppIdRole = Qt.UserRole + 11
    SubtitleRole = Qt.UserRole + 12
    GameKindRole = Qt.UserRole + 13
    CoverCardRole = Qt.UserRole + 14      # top-rounded card cover (§22 scheme B)
    CoverRoundRole = Qt.UserRole + 15     # circular list avatar (§22 scheme B)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._all_rows: list[dict[str, Any]] = []
        self._search = ""
        self._platform = ""
        self._dxtk = "all"          # all | patched | clean
        self._grouped = False       # the "all" view is split by DXVK state
        saved = str(settings.get("games_sort") or "name:asc").split(":")
        self._sort_key = saved[0]
        self._sort_desc = len(saved) > 1 and saved[1] == "desc"

    # -- Qt API ----------------------------------------------------------
    def roleNames(self) -> dict[int, bytes]:  # noqa: N802 - Qt naming
        return {
            self.KeyRole: b"gameKey",
            self.NameRole: b"name",
            self.PlatformRole: b"platform",
            self.PlatformLabelRole: b"platformLabel",
            self.Direct3DRole: b"direct3d",
            self.ArchRole: b"arch",
            self.StatusRole: b"statusText",
            self.StatusKindRole: b"statusKind",
            self.CoverRole: b"coverUrl",
            self.PathRole: b"installPath",
            self.AppIdRole: b"appId",
            self.SubtitleRole: b"subtitle",
            self.GameKindRole: b"gameKind",
            self.CoverCardRole: b"coverCardUrl",
            self.CoverRoundRole: b"coverRoundUrl",
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        mapping = {
            self.KeyRole: "key",
            self.NameRole: "name",
            self.PlatformRole: "platform",
            self.PlatformLabelRole: "platformLabel",
            self.Direct3DRole: "direct3d",
            self.ArchRole: "arch",
            self.StatusRole: "statusText",
            self.StatusKindRole: "statusKind",
            self.CoverRole: "coverUrl",
            self.PathRole: "installPath",
            self.AppIdRole: "appId",
            self.SubtitleRole: "subtitle",
            self.GameKindRole: "gameKind",
            self.CoverCardRole: "coverCardUrl",
            self.CoverRoundRole: "coverRoundUrl",
        }
        field = mapping.get(role)
        return row.get(field) if field else None

    # -- helpers used by the bridge --------------------------------------
    # Colloquial names players actually search for. Only entries that are not
    # obvious from the English title are worth listing.
    SLANG: dict[str, tuple[str, ...]] = {
        "pubg: battlegrounds": ("吃鸡", "绝地求生"),
        "playerunknown's battlegrounds": ("吃鸡",),
        "the elder scrolls v: skyrim": ("老滚", "上古卷轴"),
        "the elder scrolls v: skyrim special edition": ("老滚", "上古卷轴"),
        "grand theft auto v": ("gta5", "给他爱"),
        "grand theft auto v enhanced": ("gta5", "给他爱"),
        "red dead redemption 2": ("大表哥", "荒野大镖客"),
        "counter-strike 2": ("cs2", "反恐精英"),
        "the witcher 3: wild hunt": ("巫师3", "巫师"),
        "cyberpunk 2077": ("赛博朋克",),
        "elden ring": ("老头环", "艾尔登法环"),
        "black myth: wukong": ("黑神话", "悟空"),
        "dave the diver": ("潜水员戴夫",),
        "baldur's gate 3": ("博德之门", "bg3"),
        "resident evil 4": ("生化危机",),
        "monster hunter: world": ("怪物猎人", "mhw"),
        "monster hunter wilds": ("怪物猎人", "mhwilds"),
        "hollow knight": ("空洞骑士",),
        "stardew valley": ("星露谷",),
        "terraria": ("泰拉瑞亚",),
        "it takes two": ("双人成行",),
        "a plague tale: requiem": ("瘟疫传说",),
        "metro 2033 redux": ("地铁",),
        "metro: last light redux": ("地铁",),
        "assetto corsa": ("神力科莎",),
        "ace combat 7: skies unknown": ("皇牌空战",),
        "crysis remastered": ("孤岛危机",),
        "clair obscur: expedition 33": ("光与影", "33号远征队"),
    }

    def set_games(self, games: Iterable[steam.Game]) -> None:
        self.beginResetModel()
        self._all_rows = [
            {
                "key": game.key,
                "name": game.name,
                "nameZh": "",
                "platform": game.source,
                # Translated at build time; the source label is kept alongside
                # so retranslate() can rebuild it when ui_lang changes (§28).
                # Raw "platform" stays for filtering and the QML platform color.
                "platformLabel": _tr(game.platform_label),
                "platformLabelSrc": game.platform_label,
                # Raw inspection result, kept so the badge text can be
                # re-translated on a language switch without re-scanning.
                "_status": None,
                "direct3d": "",
                "arch": "",
                "statusText": "",
                "statusKind": "muted",
                "coverUrl": _cover_url(game),
                "coverCardUrl": _cover_card_url(game),
                "coverRoundUrl": _cover_round_url(game),
                "installPath": str(game.install_dir),
                "appId": game.appid,
                "subtitle": "",
                "exists": game.exists,
                "patched": False,
                "managed": False,
            }
            for game in games
        ]
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def retranslate(self) -> None:
        """Re-apply the interface language to cached display strings (§28).

        QML qsTr() bindings refresh themselves when the translator is swapped,
        but the platform label and status badge are resolved in Python and
        stored on the row, so they need an explicit rebuild. The section
        headers in the grouped view are rebuilt by ``_apply_filter`` (it calls
        ``_tr`` live), so re-running it refreshes those too.
        """
        for row in self._all_rows:
            row["platformLabel"] = _tr(row.get("platformLabelSrc") or row["platform"])
            text, kind, _patched, _managed = _status_tuple(
                row.get("exists", True), row.get("_status")
            )
            row["statusText"] = text
            row["statusKind"] = kind
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    @staticmethod
    def search_text(row: dict[str, Any]) -> str:
        """Everything a game can be found by.

        People type "dx12", "d3d11", "巫师3" or the store name in Chinese, none
        of which appear literally in the manifest, so the row carries a widened
        haystack instead of matching the name alone.
        """
        parts = [
            row["name"],
            row.get("nameZh") or "",
            row.get("appId") or "",
            row.get("platformLabel") or "",
            row.get("installPath") or "",
            row.get("direct3d") or "",
            row.get("arch") or "",
        ]
        api = (row.get("direct3d") or "").lower()
        for number in ("9", "10", "11", "12"):
            if number in api:
                parts.append(f"dx{number} d3d{number} direct3d{number}")
        arch = (row.get("arch") or "").lower()
        if arch == "x64":
            parts.append("64 64位")
        elif arch == "x32":
            parts.append("32 32位")
        parts.extend(GameListModel.SLANG.get((row.get("name") or "").lower(), ()))
        return " ".join(parts).lower()

    def _sorted(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort the visible rows. Version-like columns use their real order."""
        key = self._sort_key

        def by_name(row: dict[str, Any]) -> tuple:
            return ((row.get("nameZh") or row.get("name") or "").lower(),)

        def by_platform(row: dict[str, Any]) -> tuple:
            return ((row.get("platformLabel") or "").lower(),
                    (row.get("name") or "").lower())

        def by_api(row: dict[str, Any]) -> tuple:
            # Direct3D 9 < 10 < 11 < 12, not the alphabetical order.
            digits = "".join(ch for ch in (row.get("direct3d") or "") if ch.isdigit())
            return (int(digits) if digits else 99, (row.get("name") or "").lower())

        def by_arch(row: dict[str, Any]) -> tuple:
            order = {"x32": 0, "x64": 1}
            return (order.get((row.get("arch") or "").lower(), 9),
                    (row.get("name") or "").lower())

        def by_state(row: dict[str, Any]) -> tuple:
            # managed < foreign (adopt) < clean - the same order as the
            # sections under the "all" view.
            if row["patched"]:
                tier = 0 if row["managed"] else 1
            else:
                tier = 2
            return (tier, (row.get("name") or "").lower())

        chooser = {"platform": by_platform, "direct3d": by_api,
                   "arch": by_arch, "dxtk": by_state}
        return sorted(rows, key=chooser.get(key, by_name), reverse=self._sort_desc)

    def set_sort_descending(self, descending: bool) -> None:
        """Explicit direction, for the filter panel's 升序 / 降序 control."""
        if self._sort_desc == bool(descending):
            return
        self._sort_desc = bool(descending)
        settings.set("games_sort", f"{self._sort_key}:{'desc' if self._sort_desc else 'asc'}")
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def set_sort(self, key: str) -> None:
        """Click a column heading: same column flips direction."""
        if key not in ("name", "platform", "direct3d", "arch", "dxtk"):
            return
        if key == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = key
            self._sort_desc = False
        settings.set("games_sort", f"{self._sort_key}:{'desc' if self._sort_desc else 'asc'}")
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    @Property(str, notify=countChanged)
    def sortKey(self) -> str:  # noqa: N802 - QML naming
        return self._sort_key

    @Property(bool, notify=countChanged)
    def sortDescending(self) -> bool:  # noqa: N802
        return self._sort_desc

    def _apply_filter(self) -> None:
        needle = self._search.strip().lower()
        platform = self._platform
        dxtk = self._dxtk
        selected = [
            row
            for row in self._all_rows
            if (not needle or needle in self.search_text(row))
            and (not platform or row["platform"] == platform)
            and (dxtk == "all"
                 or (dxtk == "patched" and row["patched"])
                 or (dxtk == "clean" and not row["patched"]))
        ]
        selected = self._sorted(selected)
        # Under "all" the wall is split into headings, the way DLSS Swapper
        # separates Steam / Epic / manually added games. A specific filter
        # already says what is shown, so headings would only add noise.
        # Three sections: tool-managed installs, foreign installs waiting to
        # be adopted, and clean folders. A foreign install is neither clean
        # nor ours - mixing it into either side hid it from view.
        if dxtk == "all" and selected:
            managed = [row for row in selected if row["patched"] and row["managed"]]
            foreign = [row for row in selected if row["patched"] and not row["managed"]]
            missing = [row for row in selected if not row["patched"]]
            sections = [
                (f"{_tr('已装 DXVK')} · {len(managed)}", managed),
                (f"{_tr('已装·未接管')} · {len(foreign)}", foreign),
                (f"{_tr('未安装')} · {len(missing)}", missing),
            ]
            present = [(label, items) for label, items in sections if items]
            if len(present) > 1:
                rows = []
                for label, items in present:
                    rows.append({"key": "", "gameKind": "header", "rowKind": "header",
                                 "name": label})
                    rows.extend(items)
                self._rows = rows
                self._grouped = True
            else:
                # A single section would just repeat the badge on every card;
                # drop the heading entirely.
                self._rows = list(present[0][1]) if present else []
                self._grouped = False
            return
        self._rows = selected
        self._grouped = False

    def apply_filter(self, search: str = "", platform: str = "", dxtk: str = "all") -> None:
        self._search = search or ""
        self._platform = platform or ""
        self._dxtk = dxtk if dxtk in ("all", "patched", "clean") else "all"
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def dxtk_counts(self) -> dict[str, int]:
        """How many games have DXVK installed, for the filter buttons."""
        patched = sum(1 for row in self._all_rows if row["patched"])
        return {"all": len(self._all_rows), "patched": patched,
                "clean": len(self._all_rows) - patched}

    def apply_state_bulk(self, items: list[tuple[str, bool, bool]]) -> None:
        """Set (patched, managed) for many games with a single view rebuild."""
        changed = False
        for key, patched, managed in items:
            index = self.find(key)
            if index < 0:
                continue
            row = self._all_rows[index]
            if row["patched"] != bool(patched) or row["managed"] != bool(managed):
                row["patched"] = bool(patched)
                row["managed"] = bool(managed)
                changed = True
        if changed:
            self.beginResetModel()
            self._apply_filter()
            self.endResetModel()
            self.countChanged.emit()

    def set_name_zh(self, key: str, name: str) -> None:
        """Attach the localized store name and re-run the filter if needed."""
        index = self.find(key)
        if index < 0 or not name:
            return
        self._all_rows[index]["nameZh"] = name
        visible = self.view_index(key)
        if visible >= 0:
            model_index = self.index(visible, 0)
            self.dataChanged.emit(model_index, model_index)
        if self._search:
            # A Chinese query may now match this game.
            self.beginResetModel()
            self._apply_filter()
            self.endResetModel()
            self.countChanged.emit()

    def platform_options(self) -> list[dict[str, Any]]:
        """Filter chips with counts, built from the full library."""
        labels = steam.PLATFORM_LABELS
        counts: dict[str, int] = {}
        order: list[str] = []
        for row in self._all_rows:
            platform = row["platform"]
            if platform not in counts:
                counts[platform] = 0
                order.append(platform)
            counts[platform] += 1
        options = [{"value": "", "label": _tr("全部"), "count": len(self._all_rows)}]
        for platform in order:
            options.append(
                {
                    "value": platform,
                    "label": _tr(labels.get(platform, platform.title())),
                    "count": counts[platform],
                }
            )
        return options if len(options) > 2 else []

    def find(self, key: str) -> int:
        """Index into the full library (headers are not in that list)."""
        for index, row in enumerate(self._all_rows):
            if row["key"] == key:
                return index
        return -1

    def view_index(self, key: str) -> int:
        """Row index inside the filtered view, or -1 when it is not shown."""
        for index, row in enumerate(self._rows):
            if row["key"] == key:
                return index
        return -1

    def row(self, key: str) -> dict[str, Any] | None:
        index = self.find(key)
        return self._all_rows[index] if index >= 0 else None

    def update(self, key: str, **fields: Any) -> None:
        index = self.find(key)
        if index < 0:
            return
        self._all_rows[index].update(fields)
        visible = self.view_index(key)
        if visible >= 0:
            model_index = self.index(visible, 0)
            self.dataChanged.emit(model_index, model_index)

    def keys(self) -> list[str]:
        """Keys of the games currently shown (section headings excluded)."""
        return [row["key"] for row in self._rows if row.get("key")]

    def key_at(self, index: int) -> str:
        if 0 <= index < len(self._rows):
            return str(self._rows[index]["key"])
        return ""

    @Slot(str, result="QVariant")
    def details(self, key: str) -> Any:
        row = self.row(key)
        if row is None:
            return {}
        return {
            "name": row["name"],
            "path": row["installPath"],
            "platform": row["platformLabel"],
            "direct3d": row["direct3d"] or _tr("未知"),
            "arch": row["arch"] or _tr("未知"),
            "status": row["statusText"] or _tr("未安装"),
            "statusKind": row["statusKind"],
        }



def _cover_url(game: steam.Game) -> str:
    """Local file URL of the full-resolution original cover.

    Used by the detail dialog, which shows the un-cropped image (§22.5).
    """
    key = covers.cover_key(game)
    try:
        candidate = covers.original_path(key)
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return candidate.as_uri()
    except OSError:
        pass
    return ""


def _cover_variant_url(game: steam.Game, path_fn: Any) -> str:
    """File URL of a pre-sliced cover variant, only when it is fresh."""
    key = covers.cover_key(game)
    try:
        candidate = path_fn(key)
        original = covers.original_path(key)
        fresh = (
            candidate.is_file()
            and candidate.stat().st_size > 256
            and original.is_file()
            and candidate.stat().st_mtime >= original.stat().st_mtime
        )
        if fresh:
            return candidate.as_uri()
    except OSError:
        pass
    return ""


def _cover_card_url(game: steam.Game) -> str:
    """Top-rounded card cover (§22 scheme B)."""
    return _cover_variant_url(game, covers.card_path)


def _cover_round_url(game: steam.Game) -> str:
    """Circular list avatar (§22 scheme B)."""
    return _cover_variant_url(game, covers.round_path)


def _tr(text: str) -> str:
    """Translate one user-visible model string (badge texts and the like)."""
    return QCoreApplication.translate("GameListModel", text)


def _status_tuple(
    exists: bool, status: installer.GameStatus | None
) -> tuple[str, str, bool, bool]:
    """(badge text, badge kind, patched, managed) for a game card.

    Split out from ``status_for`` so the bridge can keep the raw
    ``GameStatus`` on the row and re-derive the translated badge when the
    interface language changes (§28 hot-swap) without re-reading the disk.
    """
    if not exists:
        return _tr("目录缺失"), "error", False, False
    if status is None:
        return _tr("未安装"), "muted", False, False
    if status.patched:
        if status.version:
            return (f"{status.kind or 'dxvk'} {status.version}".strip(), "ok", True, True)
        # The files carry the DXVK signature but we did not install them, so
        # the version is unknown - still installed, not "clean".
        return _tr("已装·未接管"), "warn", True, False
    if status.backuped:
        return _tr("可还原"), "warn", False, True
    return _tr("未安装"), "muted", False, False


def status_for(
    game: steam.Game, status: installer.GameStatus | None = None
) -> tuple[str, str, bool, bool]:
    """(badge text, badge kind, patched, managed) for a game card.

    patched = DXVK DLLs sit in the folder (any origin); managed = this tool
    holds the ledger record. The pair splits the wall into three groups:
    managed installs, foreign installs to adopt, and clean folders.
    """
    return _status_tuple(game.exists, status or installer.inspect(game.install_dir))
