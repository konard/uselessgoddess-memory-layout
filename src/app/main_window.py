import asyncio
from PyQt6.QtWidgets import (
  QMainWindow,
  QWidget,
  QCheckBox,
  QHBoxLayout,
  QVBoxLayout,
  QLabel,
  QTableWidget,
  QTableWidgetItem,
  QPushButton,
  QPlainTextEdit,
  QComboBox,
  QLineEdit,
  QSplitter,
  QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer

from src.ui import Component, VStack, Align
from src.core.panel import StateManager, Message
from core.logging import get_logger, logging
from core.context import Context
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
    self.setWindowTitle("CS2 Panel")
    self.resize(1000, 700)

    self.context = context
    self.manager = StateManager(self.context, callback=self.reload_layout)
    self.setup_ui()
    self.setup_logging()
    self.populate_accounts_table()
    logger.debug("main window initialized.")

  def setup_ui(self):
    main_widget = QWidget()
    self.setCentralWidget(main_widget)
    main_layout = QVBoxLayout(main_widget)

    top_bar_layout = QHBoxLayout()
    self.settings_button = QPushButton("Settings")
    self.settings_button.clicked.connect(self.open_settings)
    top_bar_layout.addWidget(self.settings_button)
    top_bar_layout.addStretch()

    v_splitter = QSplitter(Qt.Orientation.Vertical)
    h_splitter = QSplitter(Qt.Orientation.Horizontal)

    accounts_container = self._create_accounts_panel()
    logs_container = self._create_logs_panel()
    self.state_panel = QWidget()

    h_splitter.addWidget(self.state_panel)
    h_splitter.addWidget(logs_container)
    h_splitter.setStretchFactor(0, 1)
    h_splitter.setStretchFactor(1, 2)

    v_splitter.addWidget(accounts_container)
    v_splitter.addWidget(h_splitter)
    v_splitter.setStretchFactor(0, 1)
    v_splitter.setStretchFactor(1, 1)

    main_layout.addLayout(top_bar_layout)
    main_layout.addWidget(v_splitter)

  def _create_accounts_panel(self) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    self.accounts_table = QTableWidget()
    self.accounts_table.setColumnCount(3)
    self.accounts_table.setHorizontalHeaderLabels(["", "Login", "Status"])
    self.accounts_table.horizontalHeader().setSectionResizeMode(
      0, QHeaderView.ResizeMode.ResizeToContents
    )
    self.accounts_table.horizontalHeader().setSectionResizeMode(
      1, QHeaderView.ResizeMode.Stretch
    )
    self.accounts_table.horizontalHeader().setSectionResizeMode(
      2, QHeaderView.ResizeMode.Stretch
    )
    self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    layout.addWidget(QLabel("Accounts"))
    layout.addWidget(self.accounts_table)
    return container

  def _create_logs_panel(self) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    filter_layout = QHBoxLayout()

    self.log_level_combo = QComboBox()
    self.log_filter_edit = QLineEdit()
    self.log_filter_edit.setPlaceholderText("Filter logs...")

    filter_layout.addWidget(QLabel("Level:"))
    filter_layout.addWidget(self.log_level_combo)
    filter_layout.addWidget(self.log_filter_edit)

    self.log_text_edit = QPlainTextEdit()
    layout.addWidget(QLabel("Logs"))
    layout.addLayout(filter_layout)
    layout.addWidget(self.log_text_edit)
    return container

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

  def populate_accounts_table(self):
    accounts = self.context.accounts()
    self.accounts_table.setRowCount(len(accounts))
    for row, acc in enumerate(accounts):
      checkbox = QCheckBox()
      checkbox.stateChanged.connect(
        lambda state, login=acc.login: self._on_selection(state, login)
      )

      cell_widget = QWidget()
      layout = QHBoxLayout(cell_widget)
      layout.addWidget(checkbox)
      layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
      layout.setContentsMargins(0, 0, 0, 0)

      self.accounts_table.setCellWidget(row, 0, cell_widget)
      self.accounts_table.setItem(row, 1, QTableWidgetItem(acc.login))
      self.accounts_table.setItem(row, 2, QTableWidgetItem("Idle"))

  def get_selected_logins(self) -> list[str]:
    selected = []
    for row in range(self.accounts_table.rowCount()):
      cell_widget = self.accounts_table.cellWidget(row, 0)
      checkbox = cell_widget.findChild(QCheckBox)
      if checkbox and checkbox.isChecked():
        selected.append(self.accounts_table.item(row, 1).text())
    return selected

  def _on_selection(self, state: int, login: str):
    if state == Qt.CheckState.Checked.value:
      self.context.account.select(login)
    else:
      self.context.account.deselect(login)

  def reload_layout(self):
    layout_content = self.manager.acquire_state().layout(
      self.context, self.dispatch_message
    )

    panel_component: Component
    if isinstance(layout_content, list):
      panel_component = VStack(*layout_content, align=Align.Top)
    else:
      panel_component = layout_content

    new_panel_widget = panel_component.into_widget()

    old_panel = self.state_panel.findChild(QWidget)
    if old_panel:
      old_panel.deleteLater()

    if not self.state_panel.layout():
      self.state_panel.setLayout(QVBoxLayout())

    self.state_panel.layout().addWidget(new_panel_widget)

  def open_settings(self):
    dialog = SettingsDialog(self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))
