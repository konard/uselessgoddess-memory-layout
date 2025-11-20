import asyncio
from PyQt6.QtWidgets import (
  QWidget,
  QHBoxLayout,
  QVBoxLayout,
  QGridLayout,
  QComboBox,
  QLineEdit,
  QTextEdit,
)
from PyQt6.QtGui import QTextOption

from core.context import Context
from core.logging import get_logger, logging
from src.core.panel import StateManager, Message
from src.ui import ButtonType, Align
from src.ui.widgets import Button, TitledPanel, AccountsTable, Switch, VStack
from src.app.log_view import LogHandler
from src.app.settings import SettingsDialog

logger = get_logger("ui.dashboard")


class DashboardTab(QWidget):
  def __init__(self, ctx: Context, manager: StateManager, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self.manager = manager

    self._setup_ui()

    # TODO: wrap with method
    self.manager._update_ui = self.reload_layout

    self.accounts_table.populate(self.ctx.accounts())

  def _setup_ui(self):
    main_hbox = QHBoxLayout(self)
    main_hbox.setSpacing(5)
    main_hbox.setContentsMargins(5, 5, 5, 5)

    content_container = QWidget()
    grid_layout = QGridLayout(content_container)
    grid_layout.setSpacing(5)

    self.state_panel = TitledPanel("Actions")
    config_panel = self._create_config_panel()
    accounts_panel = self._create_accounts_panel()
    logs_panel = self._create_logs_panel()

    main_hbox.addWidget(accounts_panel)

    grid_layout.addWidget(self.state_panel, 0, 0)
    grid_layout.addWidget(config_panel, 0, 1)
    grid_layout.addWidget(logs_panel, 1, 0, 1, 2)

    grid_layout.setColumnStretch(0, 1)
    grid_layout.setColumnStretch(1, 1)
    grid_layout.setRowStretch(0, 1)
    grid_layout.setRowStretch(1, 2)

    main_hbox.addWidget(content_container)

    main_hbox.setStretch(0, 2)  # Accounts
    main_hbox.setStretch(1, 3)  # Content

  def get_log_handler_widgets(self):
    """Возвращает виджеты, необходимые для LogHandler"""
    return self.log_text_edit, self.log_level_combo, self.log_filter_edit

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

  def _on_selection(self, is_checked: bool, login: str):
    if is_checked:
      self.ctx.account.select(login)
    else:
      self.ctx.account.deselect(login)

    count = len(self.ctx.account.selected())
    self.accounts_panel.title_label.setText(f"Accounts | Selected: {count}")

  def open_settings(self):
    dialog = SettingsDialog(self.ctx.settings, self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))

  def clear_selection(self):
    _ = self.ctx.account.capture_selected()
    # Сброс свичей в таблице (упрощенно)
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
    if container.layout():
      while container.layout().count():
        child = container.layout().takeAt(0)
        if child.widget():
          child.widget().deleteLater()
    else:
      container.setLayout(QVBoxLayout())
      container.layout().setContentsMargins(0, 0, 0, 0)

    new_content = VStack(*widgets, align=Align.Top)
    container.layout().addWidget(new_content)
