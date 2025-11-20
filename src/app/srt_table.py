from PyQt6.QtWidgets import (
  QTableWidget,
  QWidget,
  QHBoxLayout,
  QHeaderView,
  QTableWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.services import srt
from src.ui.widgets import Switch
from src.ui.theme import CURRENT_THEME


class SortableItem(QTableWidgetItem):
  def __lt__(self, other):
    val1 = self.data(Qt.ItemDataRole.UserRole)
    val2 = other.data(Qt.ItemDataRole.UserRole)

    if val1 is None or val2 is None:
      return super().__lt__(other)

    return val1 < val2


class SRTTable(QTableWidget):
  def __init__(self, on_toggle_block, parent=None):
    super().__init__(parent)
    self.on_toggle_block = on_toggle_block
    self._setup_ui()

  def _setup_ui(self):
    self.setColumnCount(3)
    self.setHorizontalHeaderLabels(["Region", "Ping", "Block"])
    self.verticalHeader().setVisible(False)
    self.setShowGrid(True)
    self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

    header = self.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    self.setSortingEnabled(True)

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

  def populate(self, routes: list[srt.Route]):
    TARGET_PING = 120

    self.setSortingEnabled(False)
    self.setRowCount(0)
    self.setRowCount(len(routes))

    for row, route in enumerate(routes):
      name_item = QTableWidgetItem(f"{route.display_name} ({route.name})")
      name_item.setForeground(QColor(CURRENT_THEME.PRIMARY_TEXT))
      self.setItem(row, 0, name_item)

      ping_text = f"{route.ping} ms" if route.ping >= 0 else "N/A"
      ping_item = SortableItem(ping_text)

      sort_value = route.ping if route.ping >= 0 else 9999
      ping_item.setData(Qt.ItemDataRole.UserRole, sort_value)

      if route.ping > 0:
        diff = abs(route.ping - TARGET_PING)
        if diff <= 20:
          color = QColor(CURRENT_THEME.ACCENT_GREEN)
        elif diff <= 40:
          color = QColor("#fabd2f")
        elif diff <= 70:
          color = QColor("#fe8019")
        else:
          color = QColor(CURRENT_THEME.ACCENT_RED)
        ping_item.setForeground(color)
      else:
        ping_item.setForeground(QColor(CURRENT_THEME.SECONDARY_TEXT))

      self.setItem(row, 1, ping_item)

      block_sort_value = 1 if route.blocked else 0
      block_item = SortableItem()
      block_item.setData(Qt.ItemDataRole.UserRole, block_sort_value)
      self.setItem(row, 2, block_item)

      switch = Switch(checked=route.blocked)
      switch.toggled.connect(
        lambda checked, r=route.name: self.on_toggle_block(r, checked)
      )

      cell_widget = QWidget()
      layout = QHBoxLayout(cell_widget)
      layout.setContentsMargins(4, 2, 4, 2)
      layout.addWidget(switch)
      layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
      self.setCellWidget(row, 2, cell_widget)

    self.setSortingEnabled(True)
