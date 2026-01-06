import asyncio
import sys

from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
  QMainWindow,
  QTabWidget,
)

from core.logging import get_logger, logging
from core.panel import StateManager
from core.process_config import ConfigService
from core.services.disconnect_worker import DisconnectWorker
from core.services.gc.gc_server_http import start_gc_server
from core.services.status_reset_service import StatusResetService
from ui.theme import CURRENT_THEME, MAIN_WINDOW_STYLESHEET

from .log_view import LogHandler, QtLogHandler
from .tabs import DashboardTab, GSITab, SRTTab

logger = get_logger("ui.main")


class MainWindow(QMainWindow):
  def __init__(self, context, parent=None):
    super().__init__(parent)
    self.setWindowTitle("YACS Panel")
    self.resize(1100, 800)
    self.setFont(QFont(CURRENT_THEME.FONT_FAMILY, CURRENT_THEME.FONT_SIZE_NORMAL))

    self.ctx = context
    self._closing = False

    self.manager = StateManager(self.ctx, callback=lambda: None)

    # FIXME: avoid this pls!
    self.status_reset_service = StatusResetService()
    self.disconnect_worker = DisconnectWorker(self.manager, self.ctx)

    self._tasks: list[asyncio.Task] = []

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

  async def start_background_services(self):
    logger.info("Starting background services...")

    self._tasks.append(asyncio.create_task(self.status_reset_service.start()))
    self._tasks.append(asyncio.create_task(self.ctx.bot.start()))
    self._tasks.append(asyncio.create_task(self.disconnect_worker.run()))
    self._tasks.append(asyncio.create_task(self.ctx.lic.start()))

    self.gc_task = asyncio.create_task(start_gc_server(self.ctx.gc))
    self._tasks.append(self.gc_task)

    self.ctx.gsi.start()

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
      from ctypes import byref, c_int, windll

      windll.dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(c_int(1)), 4
      )
    except Exception:
      pass

  def closeEvent(self, event: QCloseEvent) -> None:
    if self._closing:
      event.accept()
      return

    event.ignore()
    self._closing = True
    asyncio.create_task(self._shutdown())

  # TODO: use tipically IoC slop container
  async def _shutdown(self):
    try:
      logger.info("Starting graceful shutdown...")

      for task in self._tasks:
        if not task.done():
          task.cancel()

      if self._tasks:
        await asyncio.gather(*self._tasks, return_exceptions=True)

      self.ctx.gsi.stop()

      if self.manager.acquire_state():
        await self.manager.acquire_state().cleanup()

      ConfigService(self.ctx).unblock_steam_store()

    except Exception as e:
      logger.error(f"Error during shutdown: {e}")
    finally:
      logger.info("Shutdown complete.")
      await asyncio.sleep(0.1)
      self.close()

      import os
      import signal

      os.kill(os.getpid(), signal.SIGTERM)
