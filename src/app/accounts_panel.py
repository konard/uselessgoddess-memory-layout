import re
from PyQt6.QtWidgets import (
  QWidget,
  QVBoxLayout,
  QHBoxLayout,
  QLineEdit,
  QTableWidget,
  QHeaderView,
  QTableWidgetItem,
  QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QCursor

from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, Switch, Tooltip
from core.context import Context
from core.account.model import FarmStatus


class AccountsPanel(QWidget):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx

    self.tooltip = Tooltip(self)

    self._setup_ui()
    self._connect_signals()

    self.refresh_table()

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    top_bar = QHBoxLayout()

    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("Search login...")
    self.search_input.setStyleSheet(f"""
        QLineEdit {{
            background-color: {CURRENT_THEME.INPUT_BACKGROUND};
            color: {CURRENT_THEME.PRIMARY_TEXT};
            border: 1px solid {CURRENT_THEME.BORDER};
            border-radius: 4px;
            padding: 4px;
        }}
    """)
    self.search_input.setFixedHeight(30)

    top_bar.addWidget(self.search_input, stretch=2)

    self.btn_all = Button("All", button_type=ButtonType.DEFAULT)
    self.btn_select_4 = Button("4 Unfarmed", button_type=ButtonType.PRIMARY)
    self.btn_select_10 = Button("10 Unfarmed", button_type=ButtonType.PRIMARY)
    self.btn_clear = Button("Clear", button_type=ButtonType.DEFAULT)

    top_bar.addWidget(self.btn_all, stretch=1)
    top_bar.addWidget(self.btn_select_4, stretch=1)
    top_bar.addWidget(self.btn_select_10, stretch=1)
    top_bar.addWidget(self.btn_clear, stretch=1)

    layout.addLayout(top_bar)

    self.table = QTableWidget()
    self.table.setColumnCount(3)
    self.table.setHorizontalHeaderLabels(["Login", "Status", "XP"])

    self.table.verticalHeader().setVisible(False)
    self.table.setShowGrid(False)
    self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    self.table.setAlternatingRowColors(True)
    self.table.setMouseTracking(True)

    header = self.table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    self.table.setStyleSheet(f"""
            QTableWidget {{ 
                background-color: transparent; 
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 4px;
                alternate-background-color: {CURRENT_THEME.PANEL_BACKGROUND};
            }}
            QHeaderView::section {{ 
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                color: {CURRENT_THEME.SECONDARY_TEXT};
                padding: 6px;
                border: none;
                font-weight: bold;
            }}
            QTableWidget::item {{
                border: none;
                padding: 4px; 
            }}
        """)

    layout.addWidget(self.table)

  def _connect_signals(self):
    self.search_input.textChanged.connect(self._on_search_changed)

    self.btn_all.clicked.connect(self._select_all_visible)
    self.btn_select_4.clicked.connect(lambda: self._smart_select(4))
    self.btn_select_10.clicked.connect(lambda: self._smart_select(10))
    self.btn_clear.clicked.connect(self.ctx.ui.clear_selection)

    self.ctx.ui.selection_changed.connect(self._update_toggles_from_state)
    self.table.cellEntered.connect(self._on_cell_hover)

  def refresh_table(self):
    accounts = self.ctx.accounts()
    self.table.setRowCount(len(accounts))

    for row, acc in enumerate(accounts):
      cell_widget = QWidget()
      cell_layout = QHBoxLayout(cell_widget)
      cell_layout.setContentsMargins(8, 2, 0, 2)

      switch = Switch()
      switch.toggled.connect(
        lambda checked, login=acc.login: self.ctx.ui.toggle(login, checked)
      )

      login_label = QLabel(acc.login)
      login_label.setStyleSheet(
        f"font-weight: bold; color: {CURRENT_THEME.PRIMARY_TEXT};"
      )

      cell_widget.switch = switch
      cell_widget.login_label = login_label
      cell_widget.original_login = acc.login

      cell_layout.addWidget(switch)
      cell_layout.addWidget(login_label)
      cell_layout.addStretch()

      self.table.setCellWidget(row, 0, cell_widget)

      status_enum = acc.lock.status or FarmStatus.NEED_TO_FARM
      status_text = status_enum.replace("_", " ").title()
      status_item = QTableWidgetItem(status_text)

      if status_enum == FarmStatus.FARMED:
        color = CURRENT_THEME.ACCENT_GREEN
      elif status_enum == FarmStatus.CAN_BE_LOOTED:
        color = CURRENT_THEME.ACCENT_PURPLE
      else:  # NEED_TO_FARM
        color = CURRENT_THEME.ACCENT_RED

      status_item.setForeground(QBrush(QColor(color)))
      status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      status_item.setData(Qt.ItemDataRole.UserRole, acc.login)
      self.table.setItem(row, 1, status_item)

      xp_val = f"{acc.lock.xp} XP" if acc.lock.xp is not None else "0 XP"
      xp_item = QTableWidgetItem(xp_val)
      xp_item.setForeground(QBrush(QColor(CURRENT_THEME.SECONDARY_TEXT)))
      xp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      xp_item.setData(Qt.ItemDataRole.UserRole, acc.login)
      self.table.setItem(row, 2, xp_item)

    self._update_toggles_from_state()

  def _update_toggles_from_state(self):
    selected = set(self.ctx.ui.selected_logins)
    self.table.blockSignals(True)

    for row in range(self.table.rowCount()):
      widget = self.table.cellWidget(row, 0)
      if widget and hasattr(widget, "switch"):
        item = self.table.item(row, 1)
        login = item.data(Qt.ItemDataRole.UserRole)
        is_selected = login in selected
        if widget.switch.isChecked() != is_selected:
          widget.switch.blockSignals(True)
          widget.switch.setChecked(is_selected)
          widget.switch.blockSignals(False)

    self.table.blockSignals(False)

  def _on_search_changed(self, text: str):
    search_text = text.lower().strip()

    pattern = None
    if search_text:
      pattern = re.compile(f"({re.escape(search_text)})", re.IGNORECASE)

    highlight_color = CURRENT_THEME.ACCENT_ORANGE
    border_color = CURRENT_THEME.ACCENT_YELLOW

    for row in range(self.table.rowCount()):
      widget = self.table.cellWidget(row, 0)
      if not widget:
        continue

      original_login = widget.original_login

      if not search_text:
        self.table.setRowHidden(row, False)
        widget.login_label.setText(original_login)
        continue

      if search_text in original_login.lower():
        self.table.setRowHidden(row, False)

        highlighted_html = pattern.sub(
          f"<span style='border: 1px solid {border_color}; background-color: {highlight_color}40;'>\\1</span>",
          original_login,
        )
        widget.login_label.setText(highlighted_html)
      else:
        self.table.setRowHidden(row, True)

  def _on_cell_hover(self, row: int, column: int):
    if column != 2:
      self.tooltip.hide_tip()
      return

    item = self.table.item(row, column)
    if not item:
      self.tooltip.hide_tip()
      return

    login = item.data(Qt.ItemDataRole.UserRole)
    account = self.ctx.account.accounts.get(login)
    if not account:
      self.tooltip.hide_tip()
      return

    raw_xp = account.lock.xp or 0
    level = (raw_xp // 5000) + 1
    progress_val = raw_xp % 5000

    status_enum = account.lock.status or FarmStatus.NEED_TO_FARM
    status_clean = status_enum.replace("_", " ").title()

    if status_enum == FarmStatus.FARMED:
      st_color = CURRENT_THEME.ACCENT_GREEN
    elif status_enum == FarmStatus.CAN_BE_LOOTED:
      st_color = CURRENT_THEME.ACCENT_PURPLE
    else:
      st_color = CURRENT_THEME.ACCENT_RED

    accent = CURRENT_THEME.ACCENT_BLUE
    secondary = CURRENT_THEME.SECONDARY_TEXT

    text = (
      f"<span style='color:{secondary}'>Status:</span> "
      f"<span style='color:{st_color}; font-weight:bold;'>{status_clean}</span><br>"
      f"<span style='color:{secondary}'>Rank:</span> "
      f"<span style='color:{CURRENT_THEME.PRIMARY_TEXT};'>{level}</span><br>"
      f"<span style='color:{secondary}'>Progress:</span> "
      f"<span style='color:{accent};'>{progress_val}</span> / 5000"
    )

    self.tooltip.show_tip(QCursor.pos(), text)

  def leaveEvent(self, event):
    self.tooltip.hide_tip()
    super().leaveEvent(event)

  def _select_all_visible(self):
    to_select = []

    for row in range(self.table.rowCount()):
      if not self.table.isRowHidden(row):
        item = self.table.item(row, 1)
        login = item.data(Qt.ItemDataRole.UserRole)
        to_select.append(login)

    self.ctx.ui.set_selection(to_select)

  def _smart_select(self, count: int):
    to_select = []
    accounts = self.ctx.accounts()

    for acc in accounts:
      if len(to_select) >= count:
        break
      status = acc.lock.status
      if status is None or status == FarmStatus.NEED_TO_FARM:
        to_select.append(acc.login)

    self.ctx.ui.set_selection(to_select)
