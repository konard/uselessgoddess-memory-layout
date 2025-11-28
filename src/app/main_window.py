import asyncio
from PyQt6.QtWidgets import (
  QMainWindow,
  QComboBox,
  QLineEdit,
  QWidget,
  QHBoxLayout,
  QVBoxLayout,
  QLabel,
  QGridLayout,
  QTextEdit,
  QTabWidget,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QTextOption, QCloseEvent

from core.process_config import ConfigService
from core.services.gc import start_gc_server
from core.services.status_reset_service import StatusResetService
from src.core.panel import StateManager, Message
from core.logging import get_logger, logging
from core.context import Context
from core import utils

from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, TitledPanel, Switch, VStack

from .log_view import LogHandler
from .settings import SettingsDialog
from .srt_table import SRTTable

from .tabs import DashboardTab, SRTTab, GSITab

logger = get_logger("ui.main")

STYLESHEET = f"""
  QWidget {{ 
      background-color: {CURRENT_THEME.BACKGROUND}; 
      color: {CURRENT_THEME.PRIMARY_TEXT}; 
  }}
  QTabWidget::pane {{ 
      border: none; 
      /* Если нужна тонкая линия сверху, раскомментируйте: */
      /* border-top: 1px solid {CURRENT_THEME.BORDER}; */
  }}
  QTabBar::tab {{ 
      background: {CURRENT_THEME.PANEL_BACKGROUND}; 
      color: {CURRENT_THEME.SECONDARY_TEXT}; 
      padding: 8px 20px; 
      margin-right: 2px; 
  }}
  QTabBar::tab:selected {{ 
      background: {CURRENT_THEME.INPUT_BACKGROUND}; 
      color: {CURRENT_THEME.PRIMARY_TEXT}; 
      border-bottom: 2px solid {CURRENT_THEME.ACCENT_BLUE}; 
  }}

"""


class QtLogHandler(logging.Handler):
  def __init__(self, widget: LogHandler):
    super().__init__()
    self.widget = widget

  def emit(self, record):
    QTimer.singleShot(0, lambda: self.widget.append(record))


class MainWindow(QMainWindow):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle("YACS Panel")
    self.resize(1100, 800)
    self.setFont(
      QFont(CURRENT_THEME.FONT_FAMILY, CURRENT_THEME.FONT_SIZE_NORMAL)
    )

    self.ctx = Context()
    self.manager = StateManager(self.ctx, callback=lambda: None)

    # FIXME: avoid this pls!
    asyncio.create_task(start_gc_server(self.ctx.gc))
    asyncio.create_task(self.ctx.bot.start())
    self.ctx.gsi.start()

    self.setup_ui()
    self._apply_dark_title_bar()

    try:
      self._init_tabs()
    except Exception:
      import traceback

      logger.error("failed to initialize tabs")
      logger.error(traceback.print_exc())

    self.setup_logging()

    logger.debug("main window initialized.")

  def setup_ui(self):
    self.setStyleSheet(STYLESHEET)
    self.tabs = QTabWidget()
    self.setCentralWidget(self.tabs)

  def _init_tabs(self):
    self.dashboard_tab = DashboardTab(self.ctx, self.manager)
    self.tabs.addTab(self.dashboard_tab, "Dashboard")

    self.srt_tab = SRTTab(self.ctx)
    self.tabs.addTab(self.srt_tab, "SRT")

    self.gsi_tab = GSITab(self.ctx)
    self.tabs.addTab(self.gsi_tab, "GSI")

  def setup_logging(self):
    text, combo, filt = self.dashboard_tab.get_log_handler_widgets()

    self.log_handler = LogHandler(text, combo, filt)
    qt_log_handler = QtLogHandler(self.log_handler)

    root_logger = logging.getLogger("")
    root_logger.addHandler(qt_log_handler)
    root_logger.setLevel(logging.DEBUG)
    logger.debug("UI log handler configured.")

  def _apply_dark_title_bar(self):
    try:
      # Windows 10 20H1+ / Windows 11
      DWMWA_USE_IMMERSIVE_DARK_MODE = 20
      hwnd = int(self.winId())
      from ctypes import c_int, byref, windll

      windll.dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(c_int(1)), 4
      )
    except Exception:
      pass

  def closeEvent(self, event: QCloseEvent) -> None:
    try:
      config_service = ConfigService(self.ctx)
      config_service.unblock_steam_store()
      logger.debug("steal lock removed")
      asyncio.create_task(self.ctx.bot.stop())
      logger.debug("telegram bot stopped")
      self.ctx.gsi.stop()
      logger.debug("gsi service stopped")
    except Exception:
      logger.exception("error during gracefully shutdown")
    finally:
      event.accept()
