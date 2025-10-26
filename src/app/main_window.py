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
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QTextOption

from src.core.panel import StateManager, Message
from core.logging import get_logger, logging
from core.context import Context

from src.ui import CURRENT_THEME, ButtonType, Align
from src.ui.widgets import Button, TitledPanel, AccountsTable, Switch, VStack

from .log_view import LogHandler
from .settings import SettingsDialog

logger = get_logger("ui.main")


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
    self.resize(1000, 800)
    self.setFont(
      QFont(CURRENT_THEME.FONT_FAMILY, CURRENT_THEME.FONT_SIZE_NORMAL)
    )

    self.setup_ui()
    self.setup_logging()

    self.ctx = Context()
    self.manager = StateManager(self.ctx, callback=self.reload_layout)
    self.accounts_table.populate(self.ctx.accounts())

    logger.debug("main window initialized.")

  def setup_ui(self):
    self.setStyleSheet(
      f"background-color: {CURRENT_THEME.BACKGROUND}; color: {CURRENT_THEME.PRIMARY_TEXT};"
    )
    central_widget = QWidget()
    self.setCentralWidget(central_widget)

    main_hbox_layout = QHBoxLayout(central_widget)
    main_hbox_layout.setSpacing(5)
    main_hbox_layout.setContentsMargins(5, 5, 5, 5)

    logs_panel = self._create_logs_panel()
    main_hbox_layout.addWidget(logs_panel)

    main_content_container = QWidget()
    main_grid_layout = QGridLayout(main_content_container)
    main_grid_layout.setSpacing(5)

    self.state_panel = TitledPanel("Actions")
    config_panel = self._create_config_panel()
    accounts_panel = self._create_accounts_panel()

    main_grid_layout.addWidget(self.state_panel, 0, 0)
    main_grid_layout.addWidget(config_panel, 0, 1)

    main_grid_layout.addWidget(accounts_panel, 1, 0, 1, 2)

    main_grid_layout.setColumnStretch(0, 1)
    main_grid_layout.setColumnStretch(1, 1)
    main_grid_layout.setRowStretch(0, 1)
    main_grid_layout.setRowStretch(1, 2)

    main_hbox_layout.addWidget(main_content_container)
    main_hbox_layout.setStretch(0, 2)
    main_hbox_layout.setStretch(1, 3)

  def _create_status_panel(self) -> QWidget:
    panel = TitledPanel("YACS Panel")
    layout = QVBoxLayout(panel.container)
    layout.addWidget(QLabel("Farmed this week: 0"))
    layout.addWidget(QLabel("Drop received: 0 [0/0]"))
    layout.addStretch()
    return panel

  def _create_logs_panel(self) -> QWidget:
    panel = TitledPanel("Logs")
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

    content_widget = VStack(
      Switch("Shuffle lobbies after game"),
      Button(
        "Set steam.exe path",
        on_click=lambda: logger.info("Set Steam Path clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      Button(
        "Set CS2 path",
        on_click=lambda: logger.info("Set CS2 Path clicked"),
        button_type=ButtonType.PRIMARY,
      ),
      Switch("Auto collect and send drop"),
      Switch("Start farm when launched"),
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

  def reload_layout(self):
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
    dialog = SettingsDialog(self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))
