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
from core.logging import get_logger
from core.panel import StateManager, Message
from core.services.process import ProcessService
from core.services.windows_service import WindowService
from ui import Align
from ui.theme import ButtonType
from ui.widgets import Button, TitledPanel, Switch, VStack
from app import AccountsPanel, SettingsDialog, LogHandler

logger = get_logger("ui.dashboard")


class DashboardTab(QWidget):
  def __init__(self, ctx: Context, manager: StateManager, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self.manager = manager

    self._setup_ui()

    # TODO: wrap with method
    self.manager._update_ui = self.reload_layout

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
      Button(
        "Telegram Test",
        on_click=lambda _: self._test_telegram(),
        button_type=ButtonType.DEFAULT,
      ),
      Button(
        "Kill All Runners",
        on_click=self._kill_all_runners,
        button_type=ButtonType.DEFAULT,
      ),
    )
    layout = QVBoxLayout(panel.container)
    layout.addWidget(content_widget)
    return panel

  def _kill_all_runners(self):
    ProcessService.kill_all_runners()

  def _test_telegram(self):
    asyncio.create_task(self.ctx.send_message("Test notification."))

  def _create_accounts_panel(self) -> QWidget:
    self.accounts_container = TitledPanel("Accounts")
    self.accounts_widget = AccountsPanel(self.ctx)

    layout = QVBoxLayout(self.accounts_container.container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(self.accounts_widget)

    self.ctx.ui.selection_changed.connect(self._update_header)
    return self.accounts_container

  def _update_header(self):
    count = len(self.ctx.ui.selected_logins)
    self.accounts_container.title_label.setText(f"Accounts | Selected: {count}")

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

  def open_settings(self):
    dialog = SettingsDialog(self.ctx.settings, self)
    dialog.exec()

  def dispatch_message(self, message: Message):
    asyncio.create_task(self.manager.dispatch(message))

  def reload_layout(self):
    current_state = self.manager.acquire_state()
    if not current_state:
      return

    widgets = []
    try:
      widgets = current_state.layout(self.ctx, self.dispatch_message)
    except Exception as e:
      logger.error(f"invalid layout: {e}")

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
