import json
from PyQt6.QtWidgets import (
  QDialog,
  QVBoxLayout,
  QLabel,
  QLineEdit,
  QDialogButtonBox,
)
from core.logging import get_logger

logger = get_logger("ui.settings")

SETTINGS_FILE = "settings.json"


class SettingsDialog(QDialog):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle("Settings")
    self.setMinimumWidth(300)

    self.layout = QVBoxLayout(self)

    self.api_key_label = QLabel("Steam API Key:")
    self.api_key_input = QLineEdit()
    self.layout.addWidget(self.api_key_label)
    self.layout.addWidget(self.api_key_input)

    self.button_box = QDialogButtonBox(
      QDialogButtonBox.StandardButton.Save
      | QDialogButtonBox.StandardButton.Cancel
    )
    self.button_box.accepted.connect(self.accept)
    self.button_box.rejected.connect(self.reject)
    self.layout.addWidget(self.button_box)

    self.load()

  def load(self):
    try:
      with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
        self.api_key_input.setText(settings.get("steam_api_key", ""))
      logger.info("Settings loaded.")
    except FileNotFoundError:
      logger.info("settings.json not found, using default settings.")
    except json.JSONDecodeError:
      logger.error(f"Failed to decode {SETTINGS_FILE}.")

  def accept(self):
    self.save()
    super().accept()

  def save(self):
    settings = {"steam_api_key": self.api_key_input.text()}
    try:
      with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)
      logger.info("Settings saved.")
    except Exception as e:
      logger.error(f"Failed to save settings: {e}")
