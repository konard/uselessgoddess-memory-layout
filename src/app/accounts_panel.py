import asyncio
import re

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QCursor, QIcon, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
  QAbstractItemView,
  QApplication,
  QComboBox,
  QDialog,
  QDialogButtonBox,
  QHBoxLayout,
  QHeaderView,
  QInputDialog,
  QLabel,
  QLineEdit,
  QListWidget,
  QListWidgetItem,
  QMenu,
  QMessageBox,
  QStackedWidget,
  QTableWidget,
  QTableWidgetItem,
  QToolButton,
  QToolTip,
  QVBoxLayout,
  QWidget,
)

from app.import_dialog import ImportAccountsDialog
from core.account.model import FarmStatus
from core.context import Context
from core.services.presets import Preset
from core.services.steam_login import generate_2fa_code
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, Switch, Tooltip

enum_to_color = {
  FarmStatus.NEED_TO_FARM: CURRENT_THEME.ACCENT_RED,
  FarmStatus.CAN_BE_LOOTED: CURRENT_THEME.ACCENT_PURPLE,
  FarmStatus.FARMED: CURRENT_THEME.ACCENT_GREEN,
  FarmStatus.TRADED: CURRENT_THEME.ACCENT_BLUE,
  FarmStatus.BLOCKED: CURRENT_THEME.ACCENT_ORANGE,
}


class NoScrollComboBox(QComboBox):
  def __init__(self, parent=None):
    super().__init__(parent)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

  def wheelEvent(self, event):
    if self.view().isVisible():
      super().wheelEvent(event)
    else:
      event.ignore()


class AccountLoginLabel(QLabel):
  def __init__(self, account, parent=None):
    super().__init__(account.login, parent)
    self.account = account
    self.setCursor(Qt.CursorShape.PointingHandCursor)
    self.setToolTip("ЛКМ: Копировать 2FA | ПКМ: Меню")
    self.setStyleSheet(f"font-weight: bold; color: {CURRENT_THEME.PRIMARY_TEXT};")

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self._copy_2fa()
    super().mousePressEvent(event)

  def contextMenuEvent(self, event):
    menu = QMenu(self)
    menu.setStyleSheet(f"""
        QMenu {{
            background-color: {CURRENT_THEME.PANEL_BACKGROUND};
            color: {CURRENT_THEME.PRIMARY_TEXT};
            border: 1px solid {CURRENT_THEME.BORDER};
        }}
        QMenu::item {{
            padding: 5px 20px;
        }}
        QMenu::item:selected {{
            background-color: {CURRENT_THEME.ACCENT_BLUE};
        }}
    """)

    action_2fa = QAction("Копировать 2FA", self)
    action_2fa.triggered.connect(self._copy_2fa)
    menu.addAction(action_2fa)

    menu.addSeparator()

    action_login = QAction("Копировать Логин", self)
    action_login.triggered.connect(self._copy_login)
    menu.addAction(action_login)

    action_pass = QAction("Копировать Пароль", self)
    action_pass.triggered.connect(self._copy_password)
    menu.addAction(action_pass)

    menu.exec(event.globalPos())

  def _copy_2fa(self):
    try:
      if not self.account.shared_secret:
        QToolTip.showText(QCursor.pos(), "Нет shared_secret!", self)
        return

      code = generate_2fa_code(self.account.shared_secret)
      QApplication.clipboard().setText(code)

      # Показываем тултип прямо у курсора
      QToolTip.showText(QCursor.pos(), f"2FA: {code} (Скопировано)", self)

    except Exception as e:
      print(f"Error generating 2FA: {e}")
      QToolTip.showText(QCursor.pos(), "Ошибка генерации 2FA", self)

  def _copy_login(self):
    QApplication.clipboard().setText(self.account.login)
    QToolTip.showText(QCursor.pos(), "Логин скопирован", self)

  def _copy_password(self):
    QApplication.clipboard().setText(self.account.password)
    QToolTip.showText(QCursor.pos(), "Пароль скопирован", self)


class AccountSelectionDialog(QDialog):
  def __init__(self, accounts: list[str], parent=None):
    super().__init__(parent)
    self.setWindowTitle("Select Account")
    self.accounts = accounts
    self.selected_account = None
    self.setFixedWidth(400)
    self.setFixedHeight(500)
    self._setup_ui()
    self._setup_styles()

  def _setup_styles(self):
    self.setStyleSheet(f"""
            QDialog {{
                background-color: {CURRENT_THEME.BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
            }}
            QListWidget {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 4px;
                color: {CURRENT_THEME.PRIMARY_TEXT};
            }}
            QListWidget::item:selected {{
                background-color: {CURRENT_THEME.ACCENT_BLUE}40;
                border: 1px solid {CURRENT_THEME.ACCENT_BLUE};
            }}
            QLineEdit {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)

  def _setup_ui(self):
    layout = QVBoxLayout(self)

    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("Search...")
    self.search_input.textChanged.connect(self._filter_list)
    layout.addWidget(self.search_input)

    self.list_widget = QListWidget()
    self.list_widget.addItems(self.accounts)
    self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.list_widget.itemDoubleClicked.connect(self.accept)
    layout.addWidget(self.list_widget)

    buttons = QDialogButtonBox(
      QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(self.accept)
    buttons.rejected.connect(self.reject)
    layout.addWidget(buttons)

  def _filter_list(self, text):
    text = text.lower()
    for i in range(self.list_widget.count()):
      item = self.list_widget.item(i)
      item.setHidden(text not in item.text().lower())

  def accept(self):
    current_item = self.list_widget.currentItem()
    if current_item:
      self.selected_account = current_item.text()
      super().accept()
    else:
      # If no item selected but only one visible, select it
      visible_items = []
      for i in range(self.list_widget.count()):
        item = self.list_widget.item(i)
        if not item.isHidden():
          visible_items.append(item)

      if len(visible_items) == 1:
        self.selected_account = visible_items[0].text()
        super().accept()


class LoadingSpinner(QWidget):
  def __init__(self, parent=None, size=24):
    super().__init__(parent)
    self.setFixedSize(size, size)
    self.angle = 0
    self.renderer = QSvgRenderer("data/icons/loader.svg")
    self.timer = QTimer(self)
    self.timer.timeout.connect(self._rotate)
    self.timer.start(40)  # Smooth rotation

  def _rotate(self):
    self.angle = (self.angle + 20) % 360
    self.update()

  def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Center translation
    cx = self.width() / 2
    cy = self.height() / 2

    painter.translate(cx, cy)
    painter.rotate(self.angle)
    painter.translate(-cx, -cy)

    self.renderer.render(painter)


class BrowserWidget(QWidget):
  def __init__(self, account, parent=None):
    super().__init__(parent)
    self.account = account

    self.layout = QHBoxLayout(self)
    self.layout.setContentsMargins(0, 0, 0, 0)
    self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.stack = QStackedWidget()
    self.stack.setFixedSize(20, 20)

    self.btn_browser = QToolButton()

    icon = QIcon("data/icons/chrome.svg")
    if icon.isNull():
      icon = QIcon.fromTheme("web-browser")
    self.btn_browser.setIcon(icon)

    self.btn_browser.setFixedSize(20, 20)
    self.btn_browser.setIconSize(QSize(18, 18))

    self.btn_browser.setCursor(Qt.CursorShape.PointingHandCursor)

    self.btn_browser.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent; 
                border: none;                  
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                border: 1px solid {CURRENT_THEME.BORDER};
            }}
            QToolButton:pressed {{
                background-color: {CURRENT_THEME.BORDER};
            }}
        """)

    self.loader_container = QWidget()
    loader_layout = QVBoxLayout(self.loader_container)
    loader_layout.setContentsMargins(0, 0, 0, 0)
    loader_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    self.spinner = LoadingSpinner(size=18)
    loader_layout.addWidget(self.spinner)

    self.stack.addWidget(self.btn_browser)
    self.stack.addWidget(self.loader_container)

    self.layout.addWidget(self.stack)

  def set_loading(self, loading: bool):
    self.stack.setCurrentIndex(1 if loading else 0)


class AccountsTable(QWidget):
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

    actions_bar = QHBoxLayout()
    actions_bar.setSpacing(5)

    self.btn_import = Button("Import", button_type=ButtonType.SUCCESS)
    actions_bar.addWidget(self.btn_import)

    self.btn_all = Button("All", button_type=ButtonType.DEFAULT)
    self.btn_select_4 = Button("4 Unfarmed", button_type=ButtonType.PRIMARY)
    self.btn_select_10 = Button("10 Unfarmed", button_type=ButtonType.PRIMARY)
    self.btn_clear = Button("Clear", button_type=ButtonType.DEFAULT)

    actions_bar.addWidget(self.btn_all)
    actions_bar.addWidget(self.btn_select_4)
    actions_bar.addWidget(self.btn_select_10)
    actions_bar.addWidget(self.btn_clear)

    layout.addLayout(actions_bar)

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

    layout.addWidget(self.search_input)

    self.table = QTableWidget()
    self.table.setColumnCount(4)
    self.table.setHorizontalHeaderLabels(["Login", "Status", "XP", "Browser"])

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
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
    self.table.setColumnWidth(3, 80)

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
            QProgressBar {{
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 2px;
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                height: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {CURRENT_THEME.ACCENT_BLUE};
            }}
        """)

    layout.addWidget(self.table)

  def _connect_signals(self):
    self.btn_import.clicked.connect(self._open_import_dialog)
    self.search_input.textChanged.connect(self._on_search_changed)

    self.btn_all.clicked.connect(self._select_all_visible)
    self.btn_select_4.clicked.connect(lambda: self._smart_select(4))
    self.btn_select_10.clicked.connect(lambda: self._smart_select(10))
    self.btn_clear.clicked.connect(self.ctx.ui.clear_selection)

    self.ctx.ui.selection_changed.connect(self._update_toggles_from_state)
    self.table.cellEntered.connect(self._on_cell_hover)
    self.ctx.ui.selection_changed.connect(self.refresh_table)

  def _open_import_dialog(self):
    dialog = ImportAccountsDialog(self.ctx, self)
    if dialog.exec():
      self.refresh_table()

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

      login_label = AccountLoginLabel(acc)

      cell_widget.switch = switch
      cell_widget.login_label = login_label
      cell_widget.original_login = acc.login

      cell_layout.addWidget(switch)
      cell_layout.addWidget(login_label)
      cell_layout.addStretch()

      self.table.setCellWidget(row, 0, cell_widget)

      status_enum = acc.lock.status or FarmStatus.NEED_TO_FARM

      status_combo = NoScrollComboBox()
      status_combo.addItems(
        [
          FarmStatus.NEED_TO_FARM.replace("_", " ").title(),
          FarmStatus.CAN_BE_LOOTED.replace("_", " ").title(),
          FarmStatus.FARMED.replace("_", " ").title(),
          FarmStatus.TRADED.replace("_", " ").title(),
          FarmStatus.BLOCKED.replace("_", " ").title(),
        ]
      )

      status_text = status_enum.replace("_", " ").title()
      status_combo.blockSignals(True)
      status_combo.setCurrentText(status_text)
      status_combo.blockSignals(False)

      color = enum_to_color[status_enum]
      status_combo.setStyleSheet(f"""
        QComboBox {{
          background-color: {CURRENT_THEME.INPUT_BACKGROUND};
          color: {color};
          border: 1px solid {CURRENT_THEME.BORDER};
          border-radius: 4px;
          padding: 4px;
        }}
        QComboBox::drop-down {{
          border: none;
        }}
        QComboBox::down-arrow {{
          image: none;
          border: none;
        }}
        QComboBox QAbstractItemView {{
          background-color: {CURRENT_THEME.INPUT_BACKGROUND};
          color: {CURRENT_THEME.PRIMARY_TEXT};
          selection-background-color: {CURRENT_THEME.ACCENT_BLUE}40;
          selection-color: {CURRENT_THEME.ACCENT_BLUE};
        }}
      """)

      status_combo.setProperty("login", acc.login)
      status_combo.currentTextChanged.connect(
        lambda text, login=acc.login: self._on_status_changed(login, text)
      )

      self.table.setCellWidget(row, 1, status_combo)

      xp_val = f"{acc.lock.xp} XP" if acc.lock.xp is not None else "0 XP"
      xp_item = QTableWidgetItem(xp_val)
      xp_item.setForeground(QBrush(QColor(CURRENT_THEME.SECONDARY_TEXT)))
      xp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      xp_item.setData(Qt.ItemDataRole.UserRole, acc.login)
      self.table.setItem(row, 2, xp_item)

      # Browser Button
      btn_container = BrowserWidget(acc)
      btn_container.btn_browser.clicked.connect(
        lambda _, w=btn_container, a=acc: self._launch_browser(w, a)
      )
      self.table.setCellWidget(row, 3, btn_container)

    self._update_toggles_from_state()

  def _launch_browser(self, widget, account):
    widget.set_loading(True)

    async def task():
      try:
        from core.services.browser import BrowserService

        success, msg = await BrowserService.launch_browser(account, self.ctx.settings)

        if not success:
          QMessageBox.warning(self, "Ошибка запуска", str(msg))

      except ImportError as e:
        error_msg = f"""Не удалось импортировать модуль BrowserService.
        Возможно, отсутствуют библиотеки selenium или webdriver-manager.
        Ошибка: {e}"""
        print(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Ошибка импорта", error_msg)

      except Exception as e:
        import traceback

        traceback.print_exc()
        error_msg = f"Произошла неожиданная ошибка при запуске браузера:\n{e}"
        QMessageBox.critical(self, "Ошибка", error_msg)
      finally:
        widget.set_loading(False)

    asyncio.create_task(task())

  def _on_status_changed(self, login: str, text: str):
    account = self.ctx.account.accounts.get(login)
    if not account:
      return

    status_map_text_to_enum = {
      FarmStatus.NEED_TO_FARM.replace("_", " ").title(): FarmStatus.NEED_TO_FARM,
      FarmStatus.CAN_BE_LOOTED.replace("_", " ").title(): FarmStatus.CAN_BE_LOOTED,
      FarmStatus.FARMED.replace("_", " ").title(): FarmStatus.FARMED,
      FarmStatus.TRADED.replace("_", " ").title(): FarmStatus.TRADED,
      FarmStatus.BLOCKED.replace("_", " ").title(): FarmStatus.BLOCKED,
    }

    new_status = status_map_text_to_enum.get(text)
    if new_status:
      account.lock.status = new_status

      for row in range(self.table.rowCount()):
        status_combo = self.table.cellWidget(row, 1)
        if status_combo and status_combo.property("login") == login:
          color = enum_to_color[new_status]
          status_combo.setStyleSheet(f"""
            QComboBox {{
              background-color: {CURRENT_THEME.INPUT_BACKGROUND};
              color: {color};
              border: 1px solid {CURRENT_THEME.BORDER};
              border-radius: 4px;
              padding: 4px;
            }}
            QComboBox::drop-down {{
              border: none;
            }}
            QComboBox::down-arrow {{
              image: none;
              border: none;
            }}
            QComboBox QAbstractItemView {{
              background-color: {CURRENT_THEME.INPUT_BACKGROUND};
              color: {CURRENT_THEME.PRIMARY_TEXT};
              selection-background-color: {CURRENT_THEME.ACCENT_BLUE}40;
              selection-color: {CURRENT_THEME.ACCENT_BLUE};
            }}
          """)
          break

  def _update_toggles_from_state(self):
    selected = set(self.ctx.ui.selected_logins)
    self.table.blockSignals(True)

    for row in range(self.table.rowCount()):
      widget = self.table.cellWidget(row, 0)
      if widget and hasattr(widget, "switch"):
        status_combo = self.table.cellWidget(row, 1)
        if status_combo:
          login = status_combo.property("login")
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
          f"""
          <span 
            style='border: 1px solid {border_color}; 
            background-color: {highlight_color}40;'>\\1
          </span>
          """,
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
    level = account.lock.lvl
    progress_val = raw_xp % 5000

    status_enum = account.lock.status or FarmStatus.NEED_TO_FARM
    status_clean = status_enum.replace("_", " ").title()

    if status_enum == FarmStatus.FARMED:
      st_color = CURRENT_THEME.ACCENT_GREEN
    elif status_enum == FarmStatus.CAN_BE_LOOTED:
      st_color = CURRENT_THEME.ACCENT_PURPLE
    elif status_enum == FarmStatus.TRADED:
      st_color = CURRENT_THEME.ACCENT_BLUE
    elif status_enum == FarmStatus.BLOCKED:
      st_color = CURRENT_THEME.ACCENT_ORANGE
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
        status_combo = self.table.cellWidget(row, 1)
        if status_combo:
          login = status_combo.property("login")
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


class DraggableListWidget(QListWidget):
  itemDropped = pyqtSignal()

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.setAcceptDrops(True)
    self.setDragEnabled(True)
    self.setDropIndicatorShown(True)

  def dropEvent(self, event):
    super().dropEvent(event)
    self.itemDropped.emit()


class PresetsView(QWidget):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self._setup_ui()
    self._connect_signals()
    self.refresh_presets()

  def _setup_ui(self):
    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)

    # Left side: Presets List
    left_widget = QWidget()
    left_layout = QVBoxLayout(left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)

    self.preset_list = QListWidget()
    self.preset_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 4px;
                color: {CURRENT_THEME.PRIMARY_TEXT};
            }}
            QListWidget::item {{
                padding: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {CURRENT_THEME.ACCENT_BLUE}40;
                border: 1px solid {CURRENT_THEME.ACCENT_BLUE};
            }}
        """)

    self.btn_create = Button("Create", button_type=ButtonType.SUCCESS)
    self.btn_delete = Button("Delete", button_type=ButtonType.DANGER)

    btns_layout = QHBoxLayout()
    btns_layout.addWidget(self.btn_create)
    btns_layout.addWidget(self.btn_delete)

    left_layout.addWidget(QLabel("Presets"))
    left_layout.addWidget(self.preset_list)
    left_layout.addLayout(btns_layout)

    # Right side: Accounts in Preset
    right_widget = QWidget()
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)

    self.account_list = DraggableListWidget()
    self.account_list.setStyleSheet(self.preset_list.styleSheet())

    self.btn_add_acc = Button("Add Account", button_type=ButtonType.PRIMARY)
    self.btn_remove_acc = Button("Remove", button_type=ButtonType.DANGER)

    acc_btns_layout = QHBoxLayout()
    acc_btns_layout.addWidget(self.btn_add_acc)
    acc_btns_layout.addWidget(self.btn_remove_acc)

    right_layout.addWidget(QLabel("Accounts in Preset (Drag to reorder)"))
    right_layout.addWidget(self.account_list)
    right_layout.addLayout(acc_btns_layout)

    layout.addWidget(left_widget, 1)
    layout.addWidget(right_widget, 2)

  def _connect_signals(self):
    self.btn_create.clicked.connect(self._create_preset)
    self.btn_delete.clicked.connect(self._delete_preset)
    self.btn_add_acc.clicked.connect(self._add_account)
    self.btn_remove_acc.clicked.connect(self._remove_account)

    self.preset_list.currentItemChanged.connect(self._on_preset_selected)
    self.account_list.itemDropped.connect(self._on_accounts_reordered)

  def refresh_presets(self):
    current_row = self.preset_list.currentRow()
    self.preset_list.clear()

    presets = self.ctx.presets.get_all_presets()
    for preset in presets:
      status = preset.get_status(self.ctx)
      color = enum_to_color.get(status, CURRENT_THEME.PRIMARY_TEXT)

      # Text label: Name (N/10)
      count = len(preset.accounts)
      text = f"{preset.name} ({count})"
      if not preset.is_valid:
        text += " ⚠️"

      item = QListWidgetItem(text)
      item.setData(Qt.ItemDataRole.UserRole, preset)
      item.setForeground(QBrush(QColor(color)))

      self.preset_list.addItem(item)

    if current_row >= 0 and current_row < self.preset_list.count():
      self.preset_list.setCurrentRow(current_row)

  def _create_preset(self):
    name, ok = QInputDialog.getText(self, "Create Preset", "Preset Name:")
    if ok:
      if self.ctx.presets.create_preset(name):
        self.refresh_presets()
      else:
        QMessageBox.warning(self, "Error", "Preset already exists!")

  def _delete_preset(self):
    item = self.preset_list.currentItem()
    if not item:
      return

    preset: Preset = item.data(Qt.ItemDataRole.UserRole)
    confirm = QMessageBox.question(
      self,
      "Confirm",
      f"Delete preset '{preset.name}'?",
      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )

    if confirm == QMessageBox.StandardButton.Yes:
      self.ctx.presets.delete_preset(preset.name)
      self.refresh_presets()
      self.account_list.clear()
      self.ctx.ui.clear_selection()

  def _on_preset_selected(self, current, previous):
    self.account_list.clear()
    if not current:
      return

    preset: Preset = current.data(Qt.ItemDataRole.UserRole)
    for i, login in enumerate(preset.accounts):
      role = ""
      if len(preset.accounts) == 4:  # 2x2 logic
        if i == 0:
          role = " [Leader A]"
        elif i == 1:
          role = " [Member A]"
        elif i == 2:
          role = " [Leader B]"
        elif i == 3:
          role = " [Member B]"
      elif len(preset.accounts) == 10:  # 5x5 logic
        if i == 0:
          role = " [Leader A]"
        elif 1 <= i <= 4:
          role = " [Member A]"
        elif i == 5:
          role = " [Leader B]"
        elif 6 <= i <= 9:
          role = " [Member B]"

      item_text = f"{login}{role}"
      item = QListWidgetItem(item_text)
      item.setData(Qt.ItemDataRole.UserRole, login)  # Store raw login
      self.account_list.addItem(item)

    # Select accounts globally for launch
    self.ctx.ui.set_selection(preset.accounts)

  def _on_accounts_reordered(self):
    item = self.preset_list.currentItem()
    if not item:
      return
    preset: Preset = item.data(Qt.ItemDataRole.UserRole)

    new_accounts = []
    for i in range(self.account_list.count()):
      login = self.account_list.item(i).data(Qt.ItemDataRole.UserRole)
      if login:
        new_accounts.append(login)

    self.ctx.presets.update_preset_accounts(preset.name, new_accounts)

    # Refresh to update labels
    # We need to temporarily block signals or restore selection carefully
    # Simple approach: call _on_preset_selected again
    self._on_preset_selected(item, None)

  def _add_account(self):
    item = self.preset_list.currentItem()
    if not item:
      QMessageBox.warning(self, "Warning", "Select a preset first.")
      return

    preset: Preset = item.data(Qt.ItemDataRole.UserRole)

    # Filter available accounts (not in any preset)
    available = []
    all_accounts = self.ctx.accounts()  # List[Account]

    for acc in all_accounts:
      used_in = self.ctx.presets.get_preset_by_account(acc.login)
      if not used_in:  # Not used anywhere
        available.append(acc.login)

    if not available:
      QMessageBox.information(
        self, "Info", "No available accounts found (all are used in presets)."
      )
      return

    dialog = AccountSelectionDialog(available, self)
    if dialog.exec() and dialog.selected_account:
      login = dialog.selected_account
      if self.ctx.presets.add_account(preset.name, login):
        # Refresh account list and presets (for count update)
        self.refresh_presets()
        # Restore selection
        for i in range(self.preset_list.count()):
          if self.preset_list.item(i).data(Qt.ItemDataRole.UserRole).name == preset.name:
            self.preset_list.setCurrentRow(i)
            break
      else:
        QMessageBox.warning(self, "Error", "Failed to add account (maybe full?).")

  def _remove_account(self):
    preset_item = self.preset_list.currentItem()
    acc_item = self.account_list.currentItem()

    if not preset_item or not acc_item:
      return

    preset: Preset = preset_item.data(Qt.ItemDataRole.UserRole)
    login = acc_item.data(Qt.ItemDataRole.UserRole)

    self.ctx.presets.remove_account(preset.name, login)

    # Refresh UI
    self.refresh_presets()
    for i in range(self.preset_list.count()):
      if self.preset_list.item(i).data(Qt.ItemDataRole.UserRole).name == preset.name:
        self.preset_list.setCurrentRow(i)
        break


class AccountsPanel(QWidget):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self._setup_ui()
    self._connect_signals()

  def _setup_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    # Mode Switcher
    mode_layout = QHBoxLayout()
    mode_layout.setSpacing(0)

    self.btn_mode_accounts = Button("All Accounts", button_type=ButtonType.PRIMARY)
    self.btn_mode_presets = Button("Presets", button_type=ButtonType.DEFAULT)

    # Styling for "tabs" look
    self.btn_mode_accounts.setFixedSize(100, 30)
    self.btn_mode_presets.setFixedSize(100, 30)

    mode_layout.addWidget(self.btn_mode_accounts)
    mode_layout.addWidget(self.btn_mode_presets)
    mode_layout.addStretch()

    layout.addLayout(mode_layout)

    self.stack = QStackedWidget()

    self.accounts_view = AccountsTable(self.ctx)
    self.presets_view = PresetsView(self.ctx)

    self.stack.addWidget(self.accounts_view)
    self.stack.addWidget(self.presets_view)

    layout.addWidget(self.stack)

  def _connect_signals(self):
    self.btn_mode_accounts.clicked.connect(lambda: self._set_mode(0))
    self.btn_mode_presets.clicked.connect(lambda: self._set_mode(1))

  def _set_mode(self, index: int):
    self.stack.setCurrentIndex(index)

    if index == 0:
      self.btn_mode_accounts._apply_style(ButtonType.PRIMARY)
      self.btn_mode_presets._apply_style(ButtonType.DEFAULT)
      self.ctx.ui.clear_selection()
    else:
      self.btn_mode_accounts._apply_style(ButtonType.DEFAULT)
      self.btn_mode_presets._apply_style(ButtonType.PRIMARY)
      # Trigger selection update for current preset
      self.presets_view._on_preset_selected(
        self.presets_view.preset_list.currentItem(), None
      )
