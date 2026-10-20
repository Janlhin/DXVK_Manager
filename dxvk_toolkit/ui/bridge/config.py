"""Configuration domain: the dxvk.conf editor, its targets and its presets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ... import confbuild, confspec, installer
from ...paths import settings
from .. import config_store
from .base import BridgeService


class ConfigService(BridgeService):
    """The generated-configuration side of the app."""

    def __init__(self, host: Any) -> None:
        super().__init__(host)
        self._model_data: Any = None
        # The config editor edits one target at a time: "" is the shared default
        # that every game inherits, otherwise a game key (normcase install dir).
        self._target: str = ""
        self._target_name: str = self.tr("默认配置")

    @property
    def model_data(self) -> Any:
        return self._model_data

    @property
    def target(self) -> str:
        return self._target

    @property
    def target_name(self) -> str:
        return self._target_name

    # -- catalogue --------------------------------------------------------
    def load_config(self) -> None:
        self._status(self.tr("正在载入 dxvk.conf 选项…"), "info")

        def work() -> Any:
            return confspec.load_model()

        def done(model: Any) -> None:
            self._model_data = model
            self._host.config.values = config_store.load_target_values(self._target)
            self._host.config.set_groups(model.groups)
            stored = str(settings.get("config_mode") or "simple")
            self._host.config.apply_filter("", stored if stored in confspec.MODES else "simple")
            self._host.configTargetChanged.emit(self._target, self._target_name)
            source = str(model.source_path) if model.source_path else self.tr("未找到参考文件")
            self._status(
                self.tr("共 {} 个选项（{}）").format(len(model.groups), source),
                "ok" if model.groups else "warn",
            )

        self._submit(work, done, self.tr("载入配置选项失败"))

    def set_option(self, key: str, enabled: bool, value: str) -> None:
        self._host.config.set_option(key, enabled, value)
        # Every edit is persisted to the active target so closing the page (or
        # the app) never loses work; only "applied to disk" is a separate step.
        config_store.persist_target_values(self._target, self._host.config.values)

    def filter_config(self, search: str, mode: str, section: str) -> None:
        self._host.config.apply_filter(search, mode, section)

    def preview_config(self) -> str:
        model = self._model_data
        if model is None:
            return "# " + self.tr("还没有载入参考文件") + "\n"
        text = confbuild.build_conf(
            model.groups,
            self._host.config.values,
            section_order=model.section_order,
            comments=bool(settings.get("conf_comments", True)),
        )
        return text

    def selected_option_count(self) -> int:
        return len([value for value in self._host.config.values.values() if value not in (None, "")])

    def modified_summary(self) -> str:
        """Human-readable summary of modified options (§33 change summary)."""
        return self._host.config.modifiedSummary()

    def reset_option(self, key: str) -> None:
        """Revert one option to default (§33 modified-list revert button)."""
        self._host.config.resetOption(key)
        # Every other edit is persisted immediately; a reset must be too, or
        # the old value comes back as soon as the target is reloaded.
        config_store.persist_target_values(self._target, self._host.config.values)
        self._status(self.tr("已还原：{}").format(key), "info")

    # -- import / export --------------------------------------------------
    def import_config(self) -> str:
        """Load an existing dxvk.conf and tick the options it contains."""
        from PySide6.QtWidgets import QFileDialog

        model = self._model_data
        if model is None:
            self._status(self.tr("还没有载入参考文件"), "warn")
            return ""
        start_dir = str(settings.get("last_export_dir") or "")
        path, _filter = QFileDialog.getOpenFileName(
            None, self.tr("导入 dxvk.conf"), start_dir, "DXVK 配置 (*.conf);;所有文件 (*)"
        )
        if not path:
            return ""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self._status(self.tr("读取失败：{}").format(exc), "error")
            return ""
        values, unknown = confspec.parse_config_values(text, model)
        self._host.config.apply_values(values)
        settings.set("last_export_dir", str(Path(path).parent))
        summary = self.tr("已从 {} 导入 {} 个选项").format(Path(path).name, len(values))
        if unknown:
            summary += self.tr("，另有 {} 个选项不在参考文件里（已忽略）").format(len(unknown))
        self._status(summary, "ok")
        return summary

    def export_config(self) -> str:
        from PySide6.QtWidgets import QFileDialog

        text = self.preview_config()
        target, _filter = QFileDialog.getSaveFileName(
            None, self.tr("导出 dxvk.conf"), "dxvk.conf", "DXVK 配置 (*.conf);;所有文件 (*)"
        )
        if not target:
            return ""
        try:
            Path(target).write_text(text, encoding="utf-8", newline="\r\n")
        except OSError as exc:
            self._status(self.tr("写入失败：{}").format(exc), "error")
            return ""
        settings.set("last_export_dir", str(Path(target).parent))
        self._status(self.tr("已导出到 {}").format(target), "ok")
        return target

    def copy_config(self) -> None:
        self._host.copyText(self.preview_config())

    def game_options(self) -> Any:
        """Games that a dxvk.conf can be written to, for the pickers."""
        options = [
            {"key": game.key, "label": game.name, "path": str(game.install_dir)}
            for game in self._host._games.values()
            if game.exists
        ]
        options.sort(key=lambda item: item["label"].lower())
        return options

    def write_conf_to_game(self, key: str) -> str:
        """Write the generated dxvk.conf next to one game's executable."""
        game = self._host._games.get(key)
        if game is None:
            self._status(self.tr("找不到这款游戏，请先扫描游戏库"), "warn")
            return ""
        text = self.preview_config()
        try:
            path = installer.write_conf(game.install_dir, text)
        except OSError as exc:
            self._status(self.tr("写入失败：{}").format(exc), "error")
            return ""
        self._status(self.tr("已写入 {}").format(path), "ok")
        self._host._library.refresh_one(game)
        return str(path)

    # -- per-game config targets ------------------------------------------
    def _reload_target(self) -> None:
        """Re-populate the model from the active target's stored selections."""
        model = self._model_data
        if model is not None:
            self._host.config.values = config_store.load_target_values(self._target)
            self._host.config.set_groups(model.groups)

    def set_config_target(self, game_key: str, name: str = "") -> None:
        """Point the config editor at the shared default ("") or one game."""
        self._target = game_key or ""
        self._target_name = name or (self.tr("默认配置") if not game_key else game_key)
        model = self._model_data
        if model is not None and game_key:
            stored = settings.get(config_store.store_key(game_key))
            if stored is None:
                # First edit of this game: start from a copy of the default so
                # the game inherits today's default instead of a blank page.
                values = config_store.load_target_values("")
                config_store.persist_target_values(game_key, values)
        self._reload_target()
        self._host.configTargetChanged.emit(self._target, self._target_name)

    def current_target(self) -> str:
        return self._target

    def current_target_name(self) -> str:
        return self._target_name

    def game_config_status(self, game_key: str) -> str:
        """Compare the edited config with the dxvk.conf on disk.

        "default" = the shared default is being edited (no disk state),
        "unknown" = game or reference not loaded, otherwise
        "not-written" / "written" / "mismatch".
        """
        if not game_key:
            return "default"
        game = self._host._games.get(game_key)
        model = self._model_data
        if game is None or model is None:
            return "unknown"
        disk = installer.read_conf(game.install_dir)
        if not disk.strip():
            return "not-written"

        def lines(text: str) -> list[str]:
            return [line.strip() for line in text.splitlines() if line.strip()]

        if game_key == self._target:
            expected = self.preview_config()
        else:
            values = config_store.load_target_values(game_key)
            if not values:
                values = config_store.load_target_values("")
            expected = confbuild.build_conf(
                model.groups,
                values,
                section_order=model.section_order,
                comments=bool(settings.get("conf_comments", True)),
            )
        return "written" if lines(disk) == lines(expected) else "mismatch"

    # -- presets -----------------------------------------------------------
    def apply_preset(self, name: str) -> int:
        """Apply a preset to the current target; returns how many options were set."""
        if name == config_store.PURE_PRESET:
            self.clear_config()
            return 0
        preset = config_store.preset_values(name)
        if not preset or self._model_data is None:
            return 0
        available = {row["key"] for row in self._host.config._all}
        applied = 0
        for key, value in preset.items():
            if key not in available:
                continue
            if isinstance(value, bool):
                self._host.config.set_option(key, value, "")
            else:
                self._host.config.set_option(key, True, str(value))
            applied += 1
        config_store.persist_target_values(self._target, self._host.config.values)
        self._reload_target()
        self._host.configTargetChanged.emit(self._target, self._target_name)
        return applied

    def list_presets(self) -> Any:
        return config_store.preset_names()

    def save_preset(self, name: str) -> None:
        name = name.strip()
        if not name or self._model_data is None:
            return
        if config_store.is_builtin(name):
            self._status(self.tr("内置预设不能覆盖，请换一个名字"), "warn")
            return
        if config_store.save_preset(name, self._host.config.values):
            self._status(self.tr("已保存预设「{}」").format(name), "ok")

    def delete_preset(self, name: str) -> None:
        config_store.delete_preset(name)

    # -- bulk actions ------------------------------------------------------
    def clear_config(self) -> None:
        """Drop every selection of the current target."""
        self._host.config.values = {}
        config_store.persist_target_values(self._target, {})
        self._reload_target()
        self._host.configTargetChanged.emit(self._target, self._target_name)

    def reset_config_to_default(self) -> None:
        """Copy the shared default over the current game's own config."""
        if not self._target:
            return
        values = config_store.load_target_values("")
        self._host.config.values = dict(values)
        config_store.persist_target_values(self._target, values)
        self._reload_target()
        self._host.configTargetChanged.emit(self._target, self._target_name)

    def toggle_section(self, label: str) -> None:
        self._host.config.toggleSection(label)

    # -- language ----------------------------------------------------------
    def refresh_target_name(self) -> None:
        """Re-derive the target label after the interface language changed.

        Switching the language while editing a game config used to rename
        that target to the shared default.
        """
        if self._target:
            game = self._host._games.get(self._target)
            self._target_name = game.name if game is not None else self._target
        else:
            self._target_name = self.tr("默认配置")
        self._host.configTargetChanged.emit(self._target, self._target_name)
