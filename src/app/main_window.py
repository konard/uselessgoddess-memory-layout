from PyQt6.QtWidgets import (
  QMainWindow,
  QWidget,
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
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from core.logging import get_logger
from core.context import Context
from .log_view import LogHandler

logger = get_logger("yacs.ui.main")


class MainWindow(QMainWindow):
  def __init__(self, context: Context, parent=None):
    super().__init__(parent)
    self.context = context

    self.setWindowTitle("CS2 Panel")
    self.resize(1000, 700)

    left_panel = self._create_accounts_panel()
    right_panel = self._create_logs_panel()

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(left_panel)
    splitter.addWidget(right_panel)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)

    self.setCentralWidget(splitter)

    self._populate_accounts_table()

  def _create_accounts_panel(self) -> QWidget:
    layout = QVBoxLayout()

    title = QLabel("Accounts")
    title.setFont(QFont("Arial", 14, QFont.Weight.Bold))

    self.accounts_table = QTableWidget()
    self.accounts_table.setColumnCount(2)
    self.accounts_table.setHorizontalHeaderLabels(["Login", "Status"])
    self.accounts_table.setSelectionBehavior(
      QTableWidget.SelectionBehavior.SelectRows
    )
    self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    header = self.accounts_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    self.start_button = QPushButton("Start Farming Selected")
    self.start_button.clicked.connect(self._start_farming)

    layout.addWidget(title)
    layout.addWidget(self.accounts_table)
    layout.addWidget(self.start_button)

    container = QWidget()
    container.setLayout(layout)
    return container

  def _create_logs_panel(self) -> QWidget:
    layout = QVBoxLayout()
    filter_layout = QHBoxLayout()

    log_level_combo = QComboBox()
    log_filter_edit = QLineEdit()
    log_filter_edit.setPlaceholderText("Filter logs...")

    filter_layout.addWidget(QLabel("Min Level:"))
    filter_layout.addWidget(log_level_combo)
    filter_layout.addWidget(log_filter_edit)

    logs_text_edit = QPlainTextEdit()

    self.log_handler = LogHandler(
      logs_text_edit, log_level_combo, log_filter_edit
    )

    clear_logs_button = QPushButton("Clear Logs")
    clear_logs_button.clicked.connect(self.log_handler.clear)

    layout.addWidget(QLabel("Logs"))
    layout.addLayout(filter_layout)
    layout.addWidget(logs_text_edit)
    layout.addWidget(clear_logs_button)

    container = QWidget()
    container.setLayout(layout)
    return container

  def _populate_accounts_table(self):
    accounts = self.context.accounts()
    self.accounts_table.setRowCount(len(accounts))

    for row, acc in enumerate(accounts):
      self.accounts_table.setItem(row, 0, QTableWidgetItem(acc.login))
      self.accounts_table.setItem(row, 1, QTableWidgetItem("Idle"))

  def _start_farming(self):
    selected_rows = self.accounts_table.selectionModel().selectedRows()
    if not selected_rows:
      logger.warn("No accounts selected to start farming.")
      return

    logins = []
    for index in selected_rows:
      login_item = self.accounts_table.item(index.row(), 0)
      logins.append(login_item.text())

      status_item = QTableWidgetItem("Farming...")
      self.accounts_table.setItem(index.row(), 1, status_item)

    logger.info(f"Starting farm for: {', '.join(logins)}")
