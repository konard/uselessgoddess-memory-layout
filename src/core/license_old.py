import sys
import urllib.request
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

from core.logging import get_logger
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button

logger = get_logger("license")


class LicenseDialog(QDialog):
  def __init__(self, title: str, html_text: str):
    super().__init__()
    self.setWindowTitle(title)
    self.setFixedWidth(400)

    self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

    self.setStyleSheet(f"""
            QDialog {{
                background-color: {CURRENT_THEME.BACKGROUND};
                border: 1px solid {CURRENT_THEME.BORDER};
            }}
            QLabel {{
                color: {CURRENT_THEME.PRIMARY_TEXT};
                font-family: "{CURRENT_THEME.FONT_FAMILY}";
                font-size: {CURRENT_THEME.FONT_SIZE_MEDIUM}pt;
            }}
        """)

    self._apply_dark_title_bar()

    layout = QVBoxLayout(self)
    layout.setSpacing(20)
    layout.setContentsMargins(20, 20, 20, 20)

    lbl_title = QLabel(title)
    lbl_title.setStyleSheet(f"""
            font-size: 14pt; 
            font-weight: bold; 
            color: {CURRENT_THEME.ACCENT_ORANGE};
        """)
    lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl_title)

    lbl_text = QLabel(html_text)
    lbl_text.setWordWrap(True)
    lbl_text.setOpenExternalLinks(True)
    lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl_text.setStyleSheet(f"""
            a {{ color: {CURRENT_THEME.ACCENT_BLUE}; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        """)
    layout.addWidget(lbl_text)

    btn_exit = Button("Exit", button_type=ButtonType.DANGER)
    btn_exit.clicked.connect(self.accept)
    layout.addWidget(btn_exit)

  def _apply_dark_title_bar(self):
    """Хак для темного заголовка окна в Windows"""
    try:
      import ctypes
      from ctypes import byref, c_int, windll

      DWMWA_USE_IMMERSIVE_DARK_MODE = 20
      hwnd = int(self.winId())
      windll.dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(c_int(1)), 4
      )
    except Exception:
      pass


def _show_styled_block_message(
  title: str, message: str, contact_link: str = "https://t.me/y_a_c_s_p"
):
  app = QApplication.instance()
  if not app:
    app = QApplication(sys.argv)

  html_text = (
    f"{message}<br><br>Contact support: <a href='{contact_link}'>t.me/y_a_c_s_p</a>"
  )

  dialog = LicenseDialog(title, html_text)
  dialog.exec()

  sys.exit(1)


def check_expiration(expiration_date: datetime):
  try:
    req = urllib.request.Request(
      "https://www.google.com",
      method="HEAD",
      headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(req, timeout=5) as response:
      date_str = response.headers["Date"]
      server_time = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
      server_now = server_time.replace(tzinfo=None)

      if server_now > expiration_date:
        logger.critical(f"License expired on {expiration_date.date()}")
        _show_styled_block_message(
          "LICENSE EXPIRED",
          f"Access denied.<br>Your license expired on <b>{expiration_date.date()}</b>.",
        )

  except Exception as e:
    logger.error(f"Network check failed: {e}")

    _show_styled_block_message(
      "SYSTEM ERROR",
      "License verification failed.<br>Please check your internet connection.",
    )

  logger.info("License verification passed.")
