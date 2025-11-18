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
from src.core.panel import StateManager, Message
from core.logging import get_logger, logging
from core.context import Context
from core import utils

from src.ui import CURRENT_THEME, ButtonType, Align
from src.ui.widgets import Button, TitledPanel, AccountsTable, Switch, VStack

from .log_view import LogHandler
from .settings import SettingsDialog
from .srt_table import SRTTable

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

    # TODO! create in main.py
    self.ctx = Context()

    asyncio.create_task(start_gc_server(self.ctx.gc))

    self.setup_ui()
    # TODO! should initialize logs before context
    self.setup_logging()

    self.manager = StateManager(self.ctx, callback=self.reload_layout)
    self.accounts_table.populate(self.ctx.accounts())

    asyncio.create_task(self._init_srt())

    self._apply_dark_title_bar()

    logger.debug("main window initialized.")

  def _apply_dark_title_bar(self):
    try:
      DWMWA_USE_IMMERSIVE_DARK_MODE = 20

      hwnd = int(self.winId())

      from ctypes import c_int, byref, windll

      windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        byref(c_int(1)),  # True
        4,  # sizeof(int)
      )
    except Exception as e:
      logger.warning(
        f"Failed to set dark title bar (very old or brand new windows version): {e}"
      )

  def setup_ui(self):
    self.setStyleSheet(STYLESHEET)

    self.tabs = QTabWidget()
    self.setCentralWidget(self.tabs)

    self.dashboard_tab = QWidget()
    self._setup_dashboard_tab(self.dashboard_tab)
    self.tabs.addTab(self.dashboard_tab, "Dashboard")

    self.utils_tab = QWidget()
    self._setup_utils_tab(self.utils_tab)
    self.tabs.addTab(self.utils_tab, "SRT")

  def _setup_dashboard_tab(self, parent_widget: QWidget):
    main_hbox_layout = QHBoxLayout(parent_widget)
    main_hbox_layout.setSpacing(5)
    main_hbox_layout.setContentsMargins(5, 5, 5, 5)

    main_content_container = QWidget()
    main_grid_layout = QGridLayout(main_content_container)
    main_grid_layout.setSpacing(5)

    self.state_panel = TitledPanel("Actions")
    config_panel = self._create_config_panel()
    accounts_panel = self._create_accounts_panel()
    logs_panel = self._create_logs_panel()

    main_hbox_layout.addWidget(accounts_panel)

    main_grid_layout.addWidget(self.state_panel, 0, 0)
    main_grid_layout.addWidget(config_panel, 0, 1)

    main_grid_layout.addWidget(logs_panel, 1, 0, 1, 2)

    main_grid_layout.setColumnStretch(0, 1)
    main_grid_layout.setColumnStretch(1, 1)
    main_grid_layout.setRowStretch(0, 1)
    main_grid_layout.setRowStretch(1, 2)

    main_hbox_layout.addWidget(main_content_container)
    main_hbox_layout.setStretch(0, 2)
    main_hbox_layout.setStretch(1, 3)

  def _setup_utils_tab(self, parent_widget: QWidget):
    layout = QHBoxLayout(parent_widget)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)

    srt_panel = self._create_srt_panel()
    layout.addWidget(srt_panel)

    layout.addStretch()

  def _create_status_panel(self) -> QWidget:
    panel = TitledPanel("YACS Panel")
    layout = QVBoxLayout(panel.container)
    layout.addWidget(QLabel("Farmed this week: 0"))
    layout.addWidget(QLabel("Drop received: 0 [0/0]"))
    layout.addStretch()
    return panel

  def _create_logs_panel(self) -> QWidget:
    panel = TitledPanel("")
    container = panel.container

    self.log_level_combo = QComboBox()
    self.log_filter_edit = QLineEdit()
    self.log_filter_edit.setPlaceholderText("Filter logs...")

    self.log_text_edit = QTextEdit()
    self.log_text_edit.setWordWrapMode(
      QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
    )

    filter_layout = QVBoxLayout()
    filter_layout.addWidget(self.log_level_combo)
    filter_layout.addWidget(self.log_filter_edit)

    main_layout = QVBoxLayout(container)
    main_layout.addLayout(filter_layout)
    main_layout.addWidget(self.log_text_edit)
    return panel

  def _create_config_panel(self) -> QWidget:
    panel = TitledPanel("Config")

    settings = self.ctx.settings
    system = settings.system

    content_widget = VStack(
      Switch(
        "Shuffle lobbies after game",
        checked=system.shuffle_lobbies,
        on_toggle=system.state_updater(settings, "shuffle_lobbies"),
      ),
      Switch(
        "Auto collect and send drop",
        checked=system.collect_drop,
        on_toggle=system.state_updater(settings, "collect_drop"),
      ),
      Switch(
        "Start farm when launched",
        checked=system.farm_on_launch,
        on_toggle=system.state_updater(settings, "farm_on_launch"),
      ),
      Button(
        "Advanced Settings",
        on_click=self.open_settings,
        button_type=ButtonType.DEFAULT,
      ),
    )

    layout = QVBoxLayout(panel.container)
    layout.addWidget(content_widget)
    return panel

  def _create_accounts_panel(self) -> QWidget:
    self.accounts_panel = TitledPanel("Accounts | Selected: 0")

    self.accounts_table = AccountsTable()

    self.accounts_table.selected.connect(self._on_selection)

    layout = QVBoxLayout(self.accounts_panel.container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(self.accounts_table)

    return self.accounts_panel

  def _create_controls_panel(self) -> QWidget:
    panel = TitledPanel("Accounts Control")
    layout = QGridLayout(panel.container)

    layout.addWidget(
      Button(
        "Start selected accounts",
        on_click=lambda: logger.info("'Start selected' clicked"),
        button_type=ButtonType.SUCCESS,
      ),
      0,
      0,
    )
    layout.addWidget(
      Button(
        "Kill selected accounts",
        on_click=lambda: logger.info("'Kill selected' clicked"),
        button_type=ButtonType.DANGER,
      ),
      1,
      0,
    )
    layout.addWidget(
      Button(
        "Select first 4 unfarmed",
        on_click=lambda: logger.info("'Select 4' clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      2,
      0,
    )
    layout.addWidget(
      Button(
        "Select first 15 unfarmed",
        on_click=lambda: logger.info("'Select 15' clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      3,
      0,
    )
    layout.addWidget(
      Button(
        "Get LVL of launched accs",
        on_click=lambda: logger.info("'Get LVL' clicked"),
        button_type=ButtonType.SUCCESS,
      ),
      4,
      0,
    )

    layout.addWidget(
      Button(
        "Move all CS windows",
        on_click=lambda: logger.info("'Move all CS' clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      0,
      1,
    )
    layout.addWidget(
      Button(
        "Kill ALL CS & Steam processes",
        on_click=lambda: logger.info("'Kill ALL' clicked"),
        button_type=ButtonType.DANGER,
      ),
      1,
      1,
    )
    layout.addWidget(
      Button(
        "Launch BES",
        on_click=lambda: logger.info("'Launch BES' clicked"),
        button_type=ButtonType.SUCCESS,
      ),
      2,
      1,
    )
    layout.addWidget(
      Button(
        "Drop stats",
        on_click=lambda: logger.info("'Drop stats' clicked"),
        button_type=ButtonType.SUCCESS,
      ),
      3,
      1,
    )
    layout.addWidget(
      Button(
        "Ban checker",
        on_click=lambda: logger.info("'Ban checker' clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      4,
      1,
    )
    layout.addWidget(
      Button(
        "Activity booster",
        on_click=lambda: logger.info("'Activity booster' clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      5,
      1,
    )

    return panel

  def _on_selection(self, is_checked: bool, login: str):
    if is_checked:
      self.ctx.account.select(login)
    else:
      self.ctx.account.deselect(login)

    selected_count = len(self.ctx.account.selected())
    self.accounts_panel.title_label.setText(
      f"Accounts | Selected: {selected_count}"
    )

  def setup_logging(self):
    self.log_handler = LogHandler(
      self.log_text_edit, self.log_level_combo, self.log_filter_edit
    )
    qt_log_handler = QtLogHandler(self.log_handler)

    root_logger = logging.getLogger("")
    root_logger.addHandler(qt_log_handler)
    root_logger.setLevel(logging.DEBUG)
    logger.debug("UI log handler configured.")

  def clear_selection(self):
    _ = self.ctx.account.capture_selected()
    logger.trace("clear selection on gui")

    for row in range(self.accounts_table.rowCount()):
      cell_widget = self.accounts_table.cellWidget(row, 0)
      if cell_widget:
        switch = cell_widget.findChild(Switch)
        if switch and switch.isChecked():
          switch.blockSignals(True)
          switch.setChecked(False)
          switch.blockSignals(False)

  def reload_layout(self):
    self.clear_selection()

    current_state = self.manager.acquire_state()
    if not current_state:
      return

    widgets = current_state.layout(self.ctx, self.dispatch_message)

    container = self.state_panel.container
    old_content = container.findChild(QWidget)
    if old_content:
      old_content.deleteLater()

    new_content = VStack(*widgets, align=Align.Top)

    if not container.layout():
      container.setLayout(QVBoxLayout())
      container.layout().setContentsMargins(0, 0, 0, 0)
    container.layout().addWidget(new_content)

  def open_settings(self):
    dialog = SettingsDialog(self.ctx.settings, self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))

  def _create_srt_panel(self) -> QWidget:
    self.srt_panel = TitledPanel("")

    self.srt_table = SRTTable(on_toggle_block=self._on_srt_block_toggle)

    layout = QVBoxLayout(self.srt_panel.container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(self.srt_table)

    btn_layout = QHBoxLayout()
    btn_layout.addWidget(
      Button(
        "Ping",
        on_click=lambda _: asyncio.create_task(self._refresh_srt_ping()),
        button_type=ButtonType.PRIMARY,
      )
    )
    btn_layout.addWidget(
      Button(
        "Clear Rules",
        on_click=self._clear_srt_rules,
        button_type=ButtonType.DANGER,
      )
    )
    layout.addLayout(btn_layout)

    return self.srt_panel

  async def _init_srt(self):
    logger.debug("loading SRT config...")
    self.srt_table.populate(
      await utils.run_blocking(self.ctx.srt.load_routes),
    )
    await self._refresh_srt_ping()

  async def _refresh_srt_ping(self, _=None):
    await self.ctx.srt.ping_all()
    self.srt_table.populate(self.ctx.srt.routes)

  def _on_srt_block_toggle(self, route_name: str, checked: bool):
    self.ctx.srt.toggle_route(route_name, checked)

  def _clear_srt_rules(self, _=None):
    self.ctx.srt.clear_all_rules()
    self.srt_table.populate(self.ctx.srt.routes)

  def closeEvent(self, event: QCloseEvent) -> None:
    """Обработчик закрытия окна - удаляет блокировку Steam Store."""
    try:
      config_service = ConfigService(self.ctx)
      config_service.unblock_steam_store()
      logger.debug("Блокировка Steam Store удалена при закрытии приложения")
    except Exception:
      logger.exception(
        "Ошибка при удалении блокировки Steam Store при закрытии"
      )
    finally:
      event.accept()
