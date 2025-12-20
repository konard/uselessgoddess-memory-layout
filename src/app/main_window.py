import sys
import asyncio
from PyQt6.QtWidgets import (
  QMainWindow,
  QTabWidget,
)
from PyQt6.QtGui import QFont, QCloseEvent

from core.process_config import ConfigService
from core.services.disconnect_worker import DisconnectWorker
from core.services.gc import start_gc_server
from core.services.status_reset_service import StatusResetService
from core.panel import StateManager
from core.logging import get_logger, logging
from ui.theme import CURRENT_THEME, MAIN_WINDOW_STYLESHEET
from .log_view import LogHandler, QtLogHandler
from .tabs import DashboardTab, SRTTab, GSITab

from core.sandbox import SandboxieInstaller


logger = get_logger("ui.main")


class MainWindow(QMainWindow):
  def __init__(self, context, parent=None):
    super().__init__(parent)
    self.setWindowTitle("YACS Panel")
    self.resize(1100, 800)
    self.setFont(
      QFont(CURRENT_THEME.FONT_FAMILY, CURRENT_THEME.FONT_SIZE_NORMAL)
    )

    self.ctx = context

    self.manager = StateManager(self.ctx, callback=lambda: None)

    # FIXME: avoid this pls!
    status_reset_service = StatusResetService()
    asyncio.create_task(status_reset_service.start())
    asyncio.create_task(start_gc_server(self.ctx.gc))
    asyncio.create_task(self.ctx.bot.start())
    disconnect_worker = DisconnectWorker(self.manager, self.ctx)
    asyncio.create_task(disconnect_worker.run())
    asyncio.create_task(self.ctx.lic.start())
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

    try:
      self._init_sandbox()
    except Exception as e:
      logger.error(f"{e}")

      from PyQt6.QtWidgets import QMessageBox

      QMessageBox.warning(
        self,
        "Sandbox Error",
        "Failed to initialize Sandbox driver.\nMulti-instance mode may not work.",
      )

    logger.debug("main window initialized.")

  def _init_sandbox(self):
    installer = SandboxieInstaller()

    logger.debug(f"use sandbox: {self.ctx.su.use_sandbox}")

    if self.ctx.su.use_sandbox:
      logger.debug("Checking Sandbox status...")
      if not installer.ensure_installed():
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.warning(
          self,
          "Sandbox Error",
          "Failed to initialize Sandbox driver.\nMulti-instance mode may not work.",
        )

  def setup_ui(self):
    self.setStyleSheet(MAIN_WINDOW_STYLESHEET)
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
      sys.exit(0)
