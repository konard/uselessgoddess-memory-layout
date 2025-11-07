from PyQt6.QtWidgets import (
  QDialog,
  QVBoxLayout,
  QFormLayout,
  QLineEdit,
  QDialogButtonBox,
)
from core.services.settings import SettingsService


class SettingsDialog(QDialog):
  def __init__(self, settings: SettingsService, parent=None):
    super().__init__(parent)
    self.settings = settings
    self.setWindowTitle("Settings")
    self.setMinimumWidth(400)

    layout = QVBoxLayout(self)
    form_layout = QFormLayout()

    self.trade_url_edit = QLineEdit()
    self.steam_path_edit = QLineEdit()
    self.cs_path_edit = QLineEdit()

    form_layout.addRow("Trade URL:", self.trade_url_edit)
    form_layout.addRow("Steam Path:", self.steam_path_edit)
    form_layout.addRow("CS2 Path:", self.cs_path_edit)
    layout.addLayout(form_layout)

    button_box = QDialogButtonBox(
      QDialogButtonBox.StandardButton.Save
      | QDialogButtonBox.StandardButton.Cancel
    )
    button_box.accepted.connect(self.accept)
    button_box.rejected.connect(self.reject)
    layout.addWidget(button_box)

    self._load_settings()

  def _load_settings(self):
    settings = self.settings.user
    self.trade_url_edit.setText(settings.trade_url)
    self.steam_path_edit.setText(settings.steam_path)
    self.cs_path_edit.setText(settings.cs_path)

  def accept(self):
    settings = self.settings.user
    settings.trade_url = self.trade_url_edit.text()
    settings.steam_path = self.steam_path_edit.text()
    settings.cs_path = self.cs_path_edit.text()

    self.settings.set_user(settings)

    super().accept()
