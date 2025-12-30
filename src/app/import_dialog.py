import json
import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
  QDialog,
  QFileDialog,
  QLabel,
  QMessageBox,
  QTextEdit,
  QVBoxLayout,
)

from core.context import Context
from core.logging import get_logger
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, Switch, TitledPanel

logger = get_logger("ui.import")

LOGPASS_FILENAME = "logpass.txt"


class FileDropZone(QLabel):
  files_dropped = pyqtSignal(list)

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setText("Drag & Drop .maFiles here\n\n(or click to select)")
    self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.setAcceptDrops(True)
    self.setMinimumHeight(150)

    self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {CURRENT_THEME.SECONDARY_TEXT};
                border-radius: 8px;
                background-color: {CURRENT_THEME.PANEL_BACKGROUND};
                color: {CURRENT_THEME.SECONDARY_TEXT};
                font-size: 12pt;
            }}
            QLabel:hover {{
                border-color: {CURRENT_THEME.ACCENT_BLUE};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
            }}
        """)

  def dragEnterEvent(self, event: QDragEnterEvent):
    if event.mimeData().hasUrls():
      event.acceptProposedAction()
      self.setStyleSheet(f"""
                QLabel {{
                    border: 2px dashed {CURRENT_THEME.ACCENT_GREEN};
                    background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                    color: {CURRENT_THEME.PRIMARY_TEXT};
                }}
            """)
    else:
      event.ignore()

  def dragLeaveEvent(self, event):
    self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {CURRENT_THEME.SECONDARY_TEXT};
                border-radius: 8px;
                background-color: {CURRENT_THEME.PANEL_BACKGROUND};
                color: {CURRENT_THEME.SECONDARY_TEXT};
            }}
        """)

  def dropEvent(self, event: QDropEvent):
    files = []
    for url in event.mimeData().urls():
      path = Path(url.toLocalFile())
      if path.is_file() and (
        path.suffix.lower() == ".mafile" or path.suffix.lower() == ".json"
      ):
        files.append(path)

    if files:
      self.files_dropped.emit(files)

    event.acceptProposedAction()

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      paths, _ = QFileDialog.getOpenFileNames(
        self, "Select maFiles", "", "MaFiles (*.maFile *.mafile *.json)"
      )
      if paths:
        self.files_dropped.emit([Path(p) for p in paths])


class ImportAccountsDialog(QDialog):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self.setWindowTitle("Import Accounts")
    self.setFixedWidth(500)
    self._setup_ui()
    self._setup_styles()

  def _setup_styles(self):
    self.setStyleSheet(f"""
            QDialog {{
                background-color: {CURRENT_THEME.BACKGROUND};
            }}
            QLabel {{
                color: {CURRENT_THEME.PRIMARY_TEXT};
            }}
            QTextEdit {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                border: 1px solid {CURRENT_THEME.BORDER};
            }}
        """)

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setSpacing(15)

    self.drop_zone = FileDropZone()
    self.drop_zone.files_dropped.connect(self._process_files)
    layout.addWidget(self.drop_zone)

    options_panel = TitledPanel("Options")
    opts_layout = QVBoxLayout(options_panel.container)

    self.sw_import_identity = Switch(
      "Import Private Data (identity_secret)", checked=True
    )
    self.sw_import_identity.setToolTip(
      "If OFF: identity_secret will be ignored (Public Mode)."
    )

    self.lbl_logpass_status = QLabel()
    if Path(LOGPASS_FILENAME).exists():
      self.lbl_logpass_status.setText(f"Found {LOGPASS_FILENAME}")
      self.lbl_logpass_status.setStyleSheet(f"color: {CURRENT_THEME.ACCENT_GREEN}")
    else:
      self.lbl_logpass_status.setText(f"❌ {LOGPASS_FILENAME} not found in root folder!")
      self.lbl_logpass_status.setStyleSheet(f"color: {CURRENT_THEME.ACCENT_RED}")

    opts_layout.addWidget(self.sw_import_identity)
    opts_layout.addWidget(self.lbl_logpass_status)

    layout.addWidget(options_panel)

    btn_close = Button(
      "Close", on_click=lambda _: self.reject(), button_type=ButtonType.DEFAULT
    )
    layout.addWidget(btn_close)

  def _load_passwords(self) -> dict[str, str]:
    """Читает logpass.txt и возвращает словарь {login_lower: password}"""
    passwords = {}
    path = Path(LOGPASS_FILENAME)

    if not path.exists():
      return {}

    try:
      with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
          line = line.strip()
          if not line:
            continue

          parts = line.split(":", 1)
          if len(parts) == 2:
            login = parts[0].strip().lower()
            password = parts[1].strip()
            passwords[login] = password
    except Exception as e:
      logger.error(f"Error reading logpass: {e}")

    return passwords

  def _process_files(self, files: list[Path]):
    pass_db = self._load_passwords()

    if not pass_db:
      QMessageBox.critical(
        self,
        "Missing Passwords",
        f"Could not load passwords from '{LOGPASS_FILENAME}'.\n"
        f"Please ensure the file exists in the root directory and has 'login:password'",
      )
      return

    success_count = 0
    skipped_logins = []

    accounts_file = Path("accounts.json")
    current_data = {}
    if accounts_file.exists():
      try:
        with open(accounts_file, encoding="utf-8") as f:
          current_data = json.load(f)
      except Exception:
        current_data = {}

    for file_path in files:
      parsed = self._parse_mafile(file_path)
      if not parsed:
        continue

      login = parsed["login"]
      normalized_login = login.lower()

      if normalized_login in pass_db:
        password = pass_db[normalized_login]
        parsed["password"] = password

        if login in current_data:
          current_data[login].update(parsed)
        else:
          current_data[login] = parsed

        success_count += 1
      else:
        skipped_logins.append(login)

    if success_count > 0:
      try:
        with open(accounts_file, "w", encoding="utf-8") as f:
          json.dump(current_data, f, indent=4, ensure_ascii=False)

        from core.services import AccountsService

        self.ctx.account = AccountsService.load()
        self.ctx.ui.selection_changed.emit()
      except Exception as e:
        logger.error(f"Failed to save accounts: {e}")
        QMessageBox.critical(self, "Error", f"Failed to save accounts.json: {e}")
        return

    self._show_report(success_count, skipped_logins)

  def _show_report(self, success: int, skipped: list[str]):
    msg = f"Successfully imported: {success} accounts.\n"

    if skipped:
      msg += f"\nSkipped {len(skipped)} accounts (missing password in {LOGPASS_FILENAME})"
      msg += ":\n"
      limit = 10
      msg += "\n".join(f"- {login}" for login in skipped[:limit])
      if len(skipped) > limit:
        msg += f"\n...and {len(skipped) - limit} more."

      self.lbl_logpass_status.setText(f"⚠ Skipped {len(skipped)} accounts!")
      self.lbl_logpass_status.setStyleSheet(f"color: {CURRENT_THEME.ACCENT_ORANGE}")

      QMessageBox.warning(self, "Import Warning", msg)
    else:
      self.lbl_logpass_status.setText(f"Success! Imported {success}")
      self.lbl_logpass_status.setStyleSheet(f"color: {CURRENT_THEME.ACCENT_GREEN}")
      QMessageBox.information(self, "Import Complete", msg)
      if success > 0:
        self.accept()

  def _parse_mafile(self, path: Path) -> dict[str, Any] | None:
    try:
      with open(path, encoding="utf-8") as f:
        data = json.load(f)

      login = data.get("account_name") or data.get("accountName") or data.get("login")

      if not login:
        return None

      steam_id = (
        data.get("SteamID")
        or data.get("steamid")
        or data.get("steam_id")
        or (data.get("Session", {}).get("SteamID"))
      )

      if not steam_id or str(steam_id) == "0":
        logger.warn(f"Skipped {path.name}: Invalid SteamID ({steam_id})")
        return None

      shared_secret = data.get("shared_secret")
      identity_secret = data.get("identity_secret")

      if not self.sw_import_identity.isChecked():
        identity_secret = None

      return {
        "login": login,
        "shared_secret": shared_secret,
        "identity_secret": identity_secret,
        "steam_id": str(steam_id) if steam_id else "0",
      }
    except Exception as e:
      logger.error(f"Failed to parse {path}: {e}")
      return None
