from PyQt6.QtWidgets import (
  QDialog,
  QVBoxLayout,
  QFormLayout,
  QLineEdit,
  QDialogButtonBox,
  QTimeEdit,
  QCheckBox,
  QHBoxLayout,
  QSpinBox,
)
from PyQt6.QtCore import QTime
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

    self.tg_token_edit = QLineEdit()
    self.tg_whitelist_edit = QLineEdit()
    self.tg_whitelist_edit.setPlaceholderText("12345678, 87654321")

    self.farm_until_check = QCheckBox("Enable")
    self.farm_until_edit = QTimeEdit()
    self.farm_until_edit.setDisplayFormat("HH:mm")
    self.farm_until_edit.setEnabled(False)
    self.farm_until_check.toggled.connect(self.farm_until_edit.setEnabled)

    farm_until_layout = QHBoxLayout()
    farm_until_layout.addWidget(self.farm_until_check)
    farm_until_layout.addWidget(self.farm_until_edit)

    self.overfarm_check = QCheckBox("Enable")
    self.overfarm_spin = QSpinBox()
    self.overfarm_spin.setRange(0, 5000)
    self.overfarm_spin.setEnabled(False)
    self.overfarm_check.toggled.connect(self.overfarm_spin.setEnabled)

    overfarm_layout = QHBoxLayout()
    overfarm_layout.addWidget(self.overfarm_check)
    overfarm_layout.addWidget(self.overfarm_spin)

    form_layout.addRow("Steam Path:", self.steam_path_edit)
    form_layout.addRow("CS2 Path:", self.cs_path_edit)
    form_layout.addRow("Trade URL:", self.trade_url_edit)
    form_layout.addRow("Telegram Token:", self.tg_token_edit)
    form_layout.addRow("TG Whitelist (comma sep):", self.tg_whitelist_edit)
    form_layout.addRow("Farm Until:", farm_until_layout)
    form_layout.addRow("Overfarm XP:", overfarm_layout)

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
    self.tg_token_edit.setText(settings.telegram_token)
    self.tg_whitelist_edit.setText(", ".join(settings.telegram_whitelist))
    if settings.farm_until:
      self.farm_until_check.setChecked(True)
      self.farm_until_edit.setEnabled(True)
      self.farm_until_edit.setTime(
        QTime.fromString(settings.farm_until, "HH:mm")
      )
    else:
      self.farm_until_check.setChecked(False)
      self.farm_until_edit.setEnabled(False)
      self.farm_until_edit.setTime(QTime.currentTime())

    if settings.overfarm is not None:
      self.overfarm_check.setChecked(True)
      self.overfarm_spin.setEnabled(True)
      self.overfarm_spin.setValue(settings.overfarm)
    else:
      self.overfarm_check.setChecked(False)
      self.overfarm_spin.setEnabled(False)
      self.overfarm_spin.setValue(0)

  def accept(self):
    settings = self.settings.user
    settings.trade_url = self.trade_url_edit.text()
    settings.steam_path = self.steam_path_edit.text()
    settings.cs_path = self.cs_path_edit.text()
    settings.telegram_token = self.tg_token_edit.text()
    raw_whitelist = self.tg_whitelist_edit.text()
    settings.telegram_whitelist = [
      x.strip() for x in raw_whitelist.split(",") if x.strip()
    ]
    if self.farm_until_check.isChecked():
      settings.farm_until = self.farm_until_edit.time().toString("HH:mm")
    else:
      settings.farm_until = None

    if self.overfarm_check.isChecked():
      settings.overfarm = self.overfarm_spin.value()
    else:
      settings.overfarm = None

    self.settings.set_user(settings)

    super().accept()
