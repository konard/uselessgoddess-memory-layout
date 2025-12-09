from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QMessageBox
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button


class LicenseInputDialog(QDialog):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle("License Activation")
    self.setFixedWidth(400)
    self.key = None
    self._setup_ui()
    self.setStyleSheet(
      f"background-color: {CURRENT_THEME.BACKGROUND}; color: {CURRENT_THEME.PRIMARY_TEXT};"
    )

  def _setup_ui(self):
    layout = QVBoxLayout(self)

    lbl = QLabel("Enter your License Key:")
    layout.addWidget(lbl)

    self.input = QLineEdit()
    self.input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
    self.input.setStyleSheet(
      f"background-color: {CURRENT_THEME.INPUT_BACKGROUND}; border: 1px solid {CURRENT_THEME.BORDER}; padding: 5px;"
    )
    layout.addWidget(self.input)

    btn = Button(
      "Activate", on_click=self._on_activate, button_type=ButtonType.PRIMARY
    )
    layout.addWidget(btn)

  def _on_activate(self, _):
    text = self.input.text().strip()
    if len(text) < 5:
      QMessageBox.warning(self, "Error", "Invalid key format")
      return
    self.key = text
    self.accept()
