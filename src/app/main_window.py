import asyncio
from PyQt6.QtWidgets import (
  QMainWindow,
  QComboBox,
  QPlainTextEdit,
  QLineEdit,
  QWidget,
  QHBoxLayout,
  QVBoxLayout,
  QLabel,
  QGridLayout,
  QHeaderView,
  QTableWidget,
  QTableWidgetItem,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

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
    QTimer.singleShot(
      0, lambda: self.widget.append(record.levelno, self.format(record))
    )


class MainWindow(QMainWindow):
  def __init__(self, context: Context, parent=None):
    super().__init__(parent)
    self.setWindowTitle("YACS Panel")
    self.resize(1000, 600)
    self.setFont(
      QFont(CURRENT_THEME.FONT_FAMILY, CURRENT_THEME.FONT_SIZE_NORMAL)
    )

    self.context = context
    self.manager = StateManager(self.context, callback=self.reload_layout)

    self.setup_ui()
    self.setup_logging()
    self.accounts_table.populate(self.context.accounts())

    logger.debug("main window initialized.")

  def setup_ui(self):
    self.setStyleSheet(
      f"background-color: {CURRENT_THEME.BACKGROUND}; color: {CURRENT_THEME.PRIMARY_TEXT};"
    )
    central_widget = QWidget()
    self.setCentralWidget(central_widget)

    main_hbox_layout = QHBoxLayout(central_widget)
    main_hbox_layout.setSpacing(10)
    main_hbox_layout.setContentsMargins(10, 10, 10, 10)

    logs_panel = self._create_logs_panel()
    main_hbox_layout.addWidget(logs_panel)

    main_content_container = QWidget()
    main_grid_layout = QGridLayout(main_content_container)
    main_grid_layout.setSpacing(10)

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
    main_hbox_layout.setStretch(0, 1)
    main_hbox_layout.setStretch(1, 2)

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
    self.log_text_edit = QPlainTextEdit()

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

    self.accounts_table.account_selected.connect(self._on_selection)

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

  def populate_accounts_list(self):
    self.accounts_table.setRowCount(0)

    accounts = self.context.accounts()
    self.accounts_table.setRowCount(len(accounts))

    mock_statuses = [
      "Farming (2v2)",
      "Idle",
      "Searching game...",
      "Connecting...",
    ]

    for row, acc in enumerate(accounts):
      switch = Switch()
      switch.toggled.connect(
        lambda checked, login=acc.login: self._on_selection(checked, login)
      )

      cell_widget = QWidget()
      cell_layout = QHBoxLayout(cell_widget)
      cell_layout.setContentsMargins(4, 4, 4, 4)
      cell_layout.addWidget(switch)
      cell_layout.addWidget(QLabel(acc.login))
      cell_layout.addStretch()

      self.accounts_table.setCellWidget(row, 0, cell_widget)

      xp_item = QTableWidgetItem(f"{row * 1250} XP")
      xp_item.setForeground(QColor(CURRENT_THEME.SECONDARY_TEXT))
      self.accounts_table.setItem(row, 1, xp_item)

      status_text = mock_statuses[row % len(mock_statuses)]
      status_item = QTableWidgetItem(status_text)

      detailed_tooltip = (
        f"Account: {acc.login}\n"
        f"Status: {status_text}\n"
        f"Session Time: 00:45:12\n"
        f"Last Drop: 2 days ago"
      )
      status_item.setToolTip(detailed_tooltip)

      self.accounts_table.setItem(row, 2, status_item)

  def _on_selection(self, login: str, is_checked: bool):
    if is_checked:
      self.context.account.select(login)
    else:
      self.context.account.deselect(login)

    selected_count = len(self.context.account.selected())
    self.accounts_panel.title_label.setText(
      f"Accounts | Selected: {selected_count}"
    )

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))

  def setup_logging(self):
    self.log_handler = LogHandler(
      self.log_text_edit, self.log_level_combo, self.log_filter_edit
    )
    qt_log_handler = QtLogHandler(self.log_handler)
    formatter = logging.Formatter("[%(levelname)s]: %(message)s")
    qt_log_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(qt_log_handler)
    root_logger.setLevel(logging.DEBUG)

  def _on_selection(self, is_checked: bool, login: str):
    if is_checked:
      self.context.account.select(login)
    else:
      self.context.account.deselect(login)

  def reload_layout(self):
    current_state = self.manager.acquire_state()
    if not current_state:
      return

    widgets = current_state.layout(self.context, self.dispatch_message)

    container = self.state_panel.container
    old_content = container.findChild(QWidget)
    if old_content:
      old_content.deleteLater()

    new_content = VStack(*widgets, align=Align.Top)

    if not container.layout():
      container.setLayout(QVBoxLayout())
      container.layout().setContentsMargins(
        0, 0, 0, 0
      )
    container.layout().addWidget(new_content)

  def open_settings(self):
    dialog = SettingsDialog(self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))
