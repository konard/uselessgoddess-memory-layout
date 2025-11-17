from PyQt6.QtWidgets import (
  QTableWidget,
  QWidget,
  QHBoxLayout,
  QLabel,
  QHeaderView,
  QTableWidgetItem,
)
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QColor, QMouseEvent

from src.ui.theme import CURRENT_THEME
from .switch import Switch
from .tooltip import Tooltip
from core.logging import get_logger

logger = get_logger("ui.widgets.accounts_table")


class AccountsTable(QTableWidget):
  selected = pyqtSignal(bool, str)

  def __init__(self, parent=None):
    super().__init__(parent)
    self._setup_ui()
    self.setMouseTracking(True)
    self.tooltip = Tooltip(self)

  def _setup_ui(self):
    self.setColumnCount(3)
    self.setHorizontalHeaderLabels(["Account", "Experience", "Status"])
    self.verticalHeader().setVisible(False)
    self.setShowGrid(True)
    self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

    header = self.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    self.setStyleSheet(f"""
            QTableWidget {{ 
                background-color: transparent; 
                border: none;
                gridline-color: {CURRENT_THEME.BORDER}; 
            }}
            QHeaderView::section {{ 
                background-color: {CURRENT_THEME.BORDER};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                padding: 4px;
                border: none;
            }}
            QTableWidget::item {{
                border-style: none;
                padding-left: 4px; 
            }}
        """)

  def populate(self, accounts: list):
    self.setRowCount(0)
    self.setRowCount(len(accounts))

    for row, acc in enumerate(accounts):
      switch = Switch()
      switch.toggled.connect(
        lambda checked, login=acc.login: self.selected.emit(checked, login)
      )
      cell_widget = QWidget()
      layout = QHBoxLayout(cell_widget)
      layout.setContentsMargins(0, 0, 0, 0)
      layout.addWidget(switch)
      layout.addWidget(QLabel(acc.login))
      layout.addStretch()
      self.setCellWidget(row, 0, cell_widget)

      xp = acc.lock.xp if acc.lock.xp is not None else 0
      xp_item = QTableWidgetItem(f"{xp} XP")
      xp_item.setForeground(QColor(CURRENT_THEME.SECONDARY_TEXT))
      self.setItem(row, 1, xp_item)

      status_text = (
        acc.lock.status
        if acc.lock.status is not None
        else "Wasn't launched yet"
      )

      status_item = QTableWidgetItem(status_text)
      detailed_tooltip = (
        f"Account: {acc.login}\n"
        f"Status: {status_text}\n"
        f"Experience: {xp} XP\n"
        f"Level: {acc.lock.lvl if acc.lock.lvl is not None else 'N/A'}"
      )

      status_item.setData(Qt.ItemDataRole.UserRole, detailed_tooltip)
      self.setItem(row, 2, status_item)

  def mouseMoveEvent(self, event: QMouseEvent):
    item = self.itemAt(event.pos())

    tooltip_text = item.data(Qt.ItemDataRole.UserRole) if item else None

    if item and item.column() == 2 and tooltip_text:
      global_pos = self.mapToGlobal(event.pos())
      self.tooltip.show_tip(global_pos, tooltip_text)
    else:
      self.tooltip.hide_tip()

    super().mouseMoveEvent(event)

  def leaveEvent(self, event: QEvent):
    self.tooltip.hide_tip()
    super().leaveEvent(event)
