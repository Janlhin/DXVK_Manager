"""Qt list models exposed to QML.

The models are plain views over data the core already produces; nothing here
talks to the network or the disk on its own.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..paths import settings

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, Qt, Signal, Slot

from .. import confspec, covers, installer, steam


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
                "platformLabel": game.platform_label,
                "direct3d": "",
                "arch": "",
                "statusText": "",
                "statusKind": "muted",
                "coverUrl": _cover_url(game),
                "installPath": str(game.install_dir),
                "appId": game.appid,
                "subtitle": "",
                "exists": game.exists,
                "patched": False,
            }
            for game in games
        ]
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
            return (0 if row["patched"] else 1, (row.get("name") or "").lower())

        chooser = {"platform": by_platform, "direct3d": by_api,
                   "arch": by_arch, "dxtk": by_state}
        return sorted(rows, key=chooser.get(key, by_name), reverse=self._sort_desc)

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
        # separates Steam / Epic / manually added games.  A specific filter
        # already says what is shown, so headings would only add noise.
        if dxtk == "all" and selected:
            installed = [row for row in selected if row["patched"]]
            missing = [row for row in selected if not row["patched"]]
            rows: list[dict[str, Any]] = []
            if installed:
                rows.append({"key": "", "gameKind": "header", "rowKind": "header",
                             "name": f"已装 DXVK · {len(installed)}"})
                rows.extend(installed)
            if missing:
                rows.append({"key": "", "gameKind": "header", "rowKind": "header",
                             "name": f"未安装 · {len(missing)}"})
                rows.extend(missing)
            self._rows = rows
            self._grouped = bool(installed and missing)
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

    def apply_patched_bulk(self, items: list[tuple[str, bool]]) -> None:
        """Set the installed flag for many games with a single view rebuild."""
        changed = False
        for key, patched in items:
            index = self.find(key)
            if index < 0:
                continue
            if self._all_rows[index]["patched"] != bool(patched):
                self._all_rows[index]["patched"] = bool(patched)
                changed = True
        if changed:
            self.beginResetModel()
            self._apply_filter()
            self.endResetModel()
            self.countChanged.emit()

    def set_patched(self, key: str, patched: bool) -> None:
        """Record whether DXVK is installed.

        Only a filter that depends on this flips the view, and when it does the
        model is reset properly: changing _rows without telling the view left
        the view holding stale indexes, which crashed the app on the next click.
        """
        index = self.find(key)
        if index < 0:
            return
        if self._all_rows[index]["patched"] == bool(patched):
            return
        self._all_rows[index]["patched"] = bool(patched)
        # The "all" view splits into 已装 / 未安装 headings, so a state change
        # moves the card between sections and the view must be rebuilt.
        if self._dxtk != "all" or self._grouped:
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
        options = [{"value": "", "label": "全部", "count": len(self._all_rows)}]
        for platform in order:
            options.append(
                {
                    "value": platform,
                    "label": labels.get(platform, platform.title()),
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
            "direct3d": row["direct3d"] or "未知",
            "arch": row["arch"] or "未知",
            "status": row["statusText"] or "未安装",
            "statusKind": row["statusKind"],
        }


class ConfigListModel(QAbstractListModel):
    """The dxvk.conf option catalogue, one row per option."""

    countChanged = Signal()

    KeyRole = Qt.UserRole + 1
    LabelRole = Qt.UserRole + 2
    DescriptionRole = Qt.UserRole + 3
    TypeRole = Qt.UserRole + 4
    ExampleRole = Qt.UserRole + 5
    SectionRole = Qt.UserRole + 6
    EnabledRole = Qt.UserRole + 7
    ValueRole = Qt.UserRole + 8
    IsBooleanRole = Qt.UserRole + 9
    SummaryRole = Qt.UserRole + 10
    KindRole = Qt.UserRole + 11
    BuildRole = Qt.UserRole + 12

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._all: list[dict[str, Any]] = []
        self._option_count = 0
        self._search = ""
        self._mode = "simple"
        self.values: dict[str, Any] = {}

    @Property(int, notify=countChanged)
    def count(self) -> int:  # noqa: A003
        return len(self._rows)

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.KeyRole: b"optionKey",
            self.LabelRole: b"label",
            self.DescriptionRole: b"description",
            self.TypeRole: b"valueType",
            self.ExampleRole: b"example",
            self.SectionRole: b"section",
            # Not "enabled": that name collides with Item.enabled and the
            # delegate then fails to instantiate at all.
            self.EnabledRole: b"optionEnabled",
            self.ValueRole: b"value",
            self.IsBooleanRole: b"isBoolean",
            self.SummaryRole: b"summary",
            self.KindRole: b"rowKind",
            self.BuildRole: b"build",
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        mapping = {
            self.KeyRole: "key",
            self.LabelRole: "label",
            self.DescriptionRole: "description",
            self.TypeRole: "type",
            self.ExampleRole: "example",
            self.SectionRole: "section",
            self.EnabledRole: "enabled",
            self.ValueRole: "value",
            self.IsBooleanRole: "isBoolean",
            self.SummaryRole: "summary",
            self.KindRole: "kind",
            self.BuildRole: "build",
        }
        field = mapping.get(role)
        return row.get(field) if field else None

    def set_groups(self, groups: Iterable[Any]) -> None:
        self.beginResetModel()
        self._all = []
        for group in groups:
            placeholder = _placeholder_for(group)
            self._all.append(
                {
                    "key": group.key,
                    "label": group.label,
                    "description": group.tooltip(),
                    "summary": group.summary(),
                    "type": group.type,
                    "example": placeholder,
                    "section": group.members[0].section if group.members else "",
                    "enabled": group.type == "boolean" and bool(self.values.get(group.key)),
                    "value": "" if group.type == "boolean" else str(self.values.get(group.key) or ""),
                    "isBoolean": group.type == "boolean",
                    "tier": confspec.tier_of(
                        group.key, group.members[0].section if group.members else ""
                    ),
                    "kind": "option",
                    "build": confspec.build_of(group.key),
                }
            )
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def apply_filter(self, search: str = "", mode: str = "simple") -> None:
        self._search = (search or "").strip().lower()
        self._mode = mode if mode in confspec.MODES else "simple"
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def _apply_filter(self) -> None:
        needle = self._search
        order = {"simple": 0, "advanced": 1, "full": 2}
        limit = order.get(self._mode, 0)
        visible: list[dict[str, Any]] = []
        for row in self._all:
            # Anything the user already ticked stays visible in every mode.
            if order.get(row["tier"], 2) > limit and not row["enabled"]:
                continue
            if needle:
                haystack = f"{row['label']} {row['key']} {row['description']}".lower()
                if needle not in haystack:
                    continue
            visible.append(row)

        rows: list[dict[str, Any]] = []
        if self._mode == "simple":
            # Group by purpose: a section header per option would just flicker
            # between dxvk / dxgi / d3d9 because most options exist in several.
            for purpose in confspec.PURPOSE_ORDER:
                bucket = [r for r in visible if confspec.purpose_of(r["key"]) == purpose]
                if not bucket:
                    continue
                rows.append({"kind": "header", "label": purpose, "key": ""})
                rows.extend(bucket)
        else:
            # Technical modes list everything grouped by section, which needs a
            # stable order to be readable.
            ordered = sorted(visible, key=lambda r: (r["section"], r["key"]))
            current = ""
            for row in ordered:
                if row["section"] != current:
                    current = row["section"]
                    rows.append({"kind": "header", "label": f"[{current}]", "key": ""})
                rows.append(row)

        self._rows = rows
        self._option_count = len(visible)

    @Property(int, notify=countChanged)
    def optionCount(self) -> int:  # noqa: N802 - QML naming
        """Option rows only (headers do not count)."""
        return getattr(self, "_option_count", len(self._rows))

    def apply_values(self, values: dict[str, Any]) -> None:
        """Replace the whole selection (used by the dxvk.conf importer)."""
        self.values = {key: value for key, value in values.items() if value not in (None, "")}
        for row in self._all:
            key = row["key"]
            if key in self.values:
                row["enabled"] = True
                row["value"] = "" if row["isBoolean"] else str(self.values[key])
            else:
                row["enabled"] = False
                row["value"] = ""
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def set_option(self, key: str, enabled: bool, value: str) -> None:
        for index, row in enumerate(self._all):
            if row["key"] != key:
                continue
            row["enabled"] = bool(enabled)
            if not row["isBoolean"]:
                row["value"] = value
            if row["isBoolean"]:
                self.values[key] = True if enabled else None
            else:
                self.values[key] = value if enabled and value.strip() else None
            try:
                position = self._rows.index(row)
            except ValueError:
                position = -1
            if position >= 0:
                model_index = self.index(position, 0)
                self.dataChanged.emit(model_index, model_index)
            return


def _placeholder_for(group: Any) -> str:
    example = str(getattr(group, "example", "") or "").strip()
    if len(example) >= 2 and example.startswith('"') and example.endswith('"'):
        return example[1:-1]
    if example in ("True", "False"):
        return ""
    return example


def _cover_url(game: steam.Game) -> str:
    """Local file URL of a cached cover, or empty when there is none."""
    key = covers.cover_key(game)
    for candidate in (covers.card_path(key), covers.original_path(key)):
        try:
            if candidate.is_file() and candidate.stat().st_size > 1024:
                return candidate.as_uri()
        except OSError:
            continue
    return ""


def status_for(game: steam.Game, status: installer.GameStatus | None = None) -> tuple[str, str]:
    """(badge text, badge kind) for a game card."""
    if not game.exists:
        return "目录缺失", "error"
    status = status or installer.inspect(game.install_dir)
    if status.patched:
        if status.version:
            return (f"{status.kind or 'dxvk'} {status.version}".strip(), "ok")
        # The files carry the DXVK signature but we did not install them, so
        # the version is unknown - still installed, not "clean".
        return "已装 DXVK", "ok"
    if status.backuped:
        return "可还原", "warn"
    return "未安装", "muted"
