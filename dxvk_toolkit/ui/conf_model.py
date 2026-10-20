"""The dxvk.conf option catalogue as a Qt list model.

Split out of :mod:`dxvk_toolkit.ui.models` so that a standalone configurator
can reuse the option list without dragging in the game library (Steam
scanning, cover art, the installer). This module only needs the pure
configuration core (:mod:`dxvk_toolkit.confkit`) and Qt.

The translation context is ``ConfigListModel`` - the group headings are the
option purposes ("framerate and sync", ...), which belong to the config
catalogue and not to the game list.
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

from ..confkit import MODES, PURPOSE_ORDER, build_of, purpose_of, tier_of

TRANSLATION_CONTEXT = "ConfigListModel"


def _tr(text: str) -> str:
    """Translate a source string under the ConfigListModel context."""
    return QCoreApplication.translate(TRANSLATION_CONTEXT, text)


class ConfigListModel(QAbstractListModel):
    """The dxvk.conf option catalogue, one row per option."""

    countChanged = Signal()
    sectionStatsChanged = Signal()

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
    DocRole = Qt.UserRole + 13

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._all: list[dict[str, Any]] = []
        self._option_count = 0
        self._search = ""
        self._mode = "simple"
        # Section header labels the user folded away (see toggleSection).
        self._collapsed: set[str] = set()
        # Category rail filter: raw purpose/section key, "" shows everything.
        self._section_filter = ""
        self._section_stats: list[dict[str, Any]] = []
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
            self.DocRole: b"doc",
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
            self.DocRole: "doc",
        }
        field = mapping.get(role)
        return row.get(field) if field else None

    def set_groups(self, groups: Iterable[Any]) -> None:
        self.beginResetModel()
        self._all = []
        for group in groups:
            placeholder = _placeholder_for(group)
            doc_summary, doc_example, doc_original = group.doc_parts()
            self._all.append(
                {
                    "key": group.key,
                    "label": group.label,
                    "description": group.tooltip(),
                    "summary": group.summary(),
                    "doc": {
                        "summary": doc_summary,
                        "example": doc_example,
                        "original": doc_original,
                    },
                    "type": group.type,
                    "example": placeholder,
                    "section": group.members[0].section if group.members else "",
                    "enabled": group.type == "boolean" and bool(self.values.get(group.key)),
                    "value": "" if group.type == "boolean" else str(self.values.get(group.key) or ""),
                    "isBoolean": group.type == "boolean",
                    "tier": tier_of(
                        group.key, group.members[0].section if group.members else ""
                    ),
                    "kind": "option",
                    "build": build_of(group.key),
                }
            )
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    def apply_filter(self, search: str = "", mode: str = "simple", section: str = "") -> None:
        self._search = (search or "").strip().lower()
        self._mode = mode if mode in MODES else "simple"
        self._section_filter = section or ""
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
        stats: list[dict[str, Any]] = []
        if self._mode == "simple":
            # Group by purpose: a section header per option would just flicker
            # between dxvk / dxgi / d3d9 because most options exist in several.
            # Buckets are computed regardless of the rail filter so the
            # category counts always reflect the current search + mode.
            for purpose in PURPOSE_ORDER:
                bucket = [r for r in visible if purpose_of(r["key"]) == purpose]
                if not bucket:
                    continue
                # The label goes through _tr so the simple mode's group
                # headings follow the interface language; the collapse set
                # stores the translated label, which stays self-consistent
                # because the state is in-memory only. The rail filters by
                # the raw purpose key so locale switches cannot orphan it.
                label = _tr(purpose)
                stats.append({"label": label, "key": purpose, "count": len(bucket)})
                if self._section_filter and purpose != self._section_filter:
                    continue
                if not self._section_filter and purpose in self._collapsed:
                    continue
                rows.append({"kind": "header", "label": label, "key": ""})
                rows.extend(bucket)
        else:
            # Technical modes list everything grouped by section, which needs a
            # stable order to be readable.
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in sorted(visible, key=lambda r: (r["section"], r["key"])):
                grouped.setdefault(row["section"], []).append(row)
            for section, bucket in grouped.items():
                stats.append({"label": section, "key": section, "count": len(bucket)})
                if self._section_filter and section != self._section_filter:
                    continue
                if not self._section_filter and section in self._collapsed:
                    continue
                rows.append({"kind": "header", "label": f"[{section}]", "key": ""})
                rows.extend(bucket)

        self._rows = rows
        self._option_count = len(visible)
        self._section_stats = stats
        self.sectionStatsChanged.emit()

    def toggleSection(self, label: str) -> None:
        """Fold/unfold one catalogue section (identified by its header label)."""
        if label in self._collapsed:
            self._collapsed.discard(label)
        else:
            self._collapsed.add(label)
        self.beginResetModel()
        self._apply_filter()
        self.endResetModel()
        self.countChanged.emit()

    @Property(int, notify=countChanged)
    def optionCount(self) -> int:  # noqa: N802 - QML naming
        """Option rows only (headers do not count)."""
        return getattr(self, "_option_count", len(self._rows))

    @Property(list, notify=sectionStatsChanged)
    def sectionStats(self) -> list[dict[str, Any]]:  # noqa: N802 - QML naming
        """Category rail data: [{label, key, count}] under the current filter."""
        return self._section_stats

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

    # --- §33: modified-options tracking (user perspective layer) ----------

    @Property(int, notify=countChanged)
    def modifiedCount(self) -> int:  # noqa: N802 - QML naming
        """How many options the user has changed from defaults."""
        return sum(1 for v in self.values.values() if v is not None and v != "")

    @Slot(result=str)
    def modifiedSummary(self) -> str:
        """Human-readable summary of what the user changed, for the preview.

        Returns one line per modified option: 'key = value (purpose)'.
        Empty string when nothing is modified.
        """
        lines: list[str] = []
        for row in self._all:
            key = row["key"]
            val = self.values.get(key)
            if val is None or val == "":
                continue
            purpose = purpose_of(key)
            display = "True" if row["isBoolean"] else str(val)
            lines.append(f"{key} = {display}  ({_tr(purpose)})")
        return "\n".join(lines)

    @Slot(str)
    def resetOption(self, key: str) -> None:  # noqa: N802 - QML naming
        """Revert a single option to its default (remove from selection)."""
        if key in self.values:
            self.values[key] = None
        for index, row in enumerate(self._all):
            if row["key"] != key:
                continue
            row["enabled"] = False
            if not row["isBoolean"]:
                row["value"] = ""
            try:
                position = self._rows.index(row)
            except ValueError:
                position = -1
            if position >= 0:
                model_index = self.index(position, 0)
                self.dataChanged.emit(model_index, model_index)
            break
        self.countChanged.emit()


def _placeholder_for(group: Any) -> str:
    example = str(getattr(group, "example", "") or "").strip()
    if len(example) >= 2 and example.startswith('"') and example.endswith('"'):
        return example[1:-1]
    if example in ("True", "False"):
        return ""
    return example
