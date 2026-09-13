"""Qt list models exposed to QML.

The models are plain views over data the core already produces; nothing here
talks to the network or the disk on its own.
"""

from __future__ import annotations

from typing import Any, Iterable

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

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._all_rows: list[dict[str, Any]] = []
        self._search = ""
        self._platform = ""
        self._dxtk = "all"          # all | patched | clean

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
        }
        field = mapping.get(role)
        return row.get(field) if field else None

    # -- helpers used by the bridge --------------------------------------
    def set_games(self, games: Iterable[steam.Game]) -> None:
        self.beginResetModel()
        self._all_rows = [
            {
                "key": game.key,
                "name": game.name,
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

    def _apply_filter(self) -> None:
        needle = self._search.strip().lower()
        platform = self._platform
        dxtk = self._dxtk
        self._rows = [
            row
            for row in self._all_rows
            if (not needle or needle in f"{row['name']} {row['appId']}".lower())
            and (not platform or row["platform"] == platform)
            and (dxtk == "all"
                 or (dxtk == "patched" and row["patched"])
                 or (dxtk == "clean" and not row["patched"]))
        ]

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
        if self._dxtk != "all":
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
        return [row["key"] for row in self._rows]

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
