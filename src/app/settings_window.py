from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QFileDialog

from src.core.config_manager import ConfigManager


class SettingsWindow(QDialog):
    """Диалог настроек путей Steam и CS2."""

    def __init__(self, config: ConfigManager, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.config = config

        ui_path = Path(__file__).resolve().parents[1] / "ui" / "settings_window.ui"
        uic.loadUi(str(ui_path), self)

        # Инициализация значений
        self.leSteamPath.setText(str(self.config.get("steam_path", "")))
        self.leCS2Path.setText(str(self.config.get("cs2_path", "")))

        # Сигналы
        self.btnBrowseSteam.clicked.connect(self._browse_steam)
        self.btnBrowseCS2.clicked.connect(self._browse_cs2)
        self.btnSave.clicked.connect(self._save)
        self.btnCancel.clicked.connect(self.reject)

    def _browse_steam(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите папку Steam")
        if path:
            self.leSteamPath.setText(path)

    def _browse_cs2(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите папку CS2")
        if path:
            self.leCS2Path.setText(path)

    def _save(self) -> None:
        self.config.set("steam_path", self.leSteamPath.text())
        self.config.set("cs2_path", self.leCS2Path.text())
        self.config.save()
        self.accept()


