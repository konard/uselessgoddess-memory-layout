import asyncio

from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
  QComboBox,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

import states
from app import AccountsPanel, SettingsDialog
from core.context import Context
from core.logging import get_logger
from core.panel import Message, StateManager
from core.services.settings import MatchMode
from core.services.status_reset_service import StatusResetService
from core.services.windows_service import WindowService
from ui import Align
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, Switch, TitledPanel, VStack

logger = get_logger("ui.dashboard")


class DashboardTab(QWidget):
  def __init__(
    self,
    ctx: Context,
    manager: StateManager,
    status_reset_service: StatusResetService,
    parent=None,
  ):
    super().__init__(parent)
    self.ctx = ctx
    self.manager = manager
    self.status_reset_service = status_reset_service
    self._sandbox_warned = False

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
    return self.log_text_edit, self.log_level_combo, self.log_filter_edit

  def _create_config_panel(self) -> QWidget:
    panel = TitledPanel("Config")
    settings = self.ctx.settings
    system = settings.system
    user = settings.user

    sw_sandbox = Switch(
      "Use NO-AVAST (EXPERIMENTAL)",
      checked=user.experimental_launch,
      active_color=CURRENT_THEME.ACCENT_BLUE,
    )
    sw_sandbox.toggled.connect(lambda c: self._on_sandbox_toggled(c, sw_sandbox))

    mode_layout = QHBoxLayout()
    mode_layout.setContentsMargins(0, 0, 0, 0)
    mode_label = QLabel("Match Strategy:")

    self.combo_mode = QComboBox()
    self.combo_mode.addItems(["Tie (8:8)", "Random"])

    current_mode_idx = 0 if user.match_mode == MatchMode.TIE else 1
    self.combo_mode.setCurrentIndex(current_mode_idx)

    self.combo_mode.currentIndexChanged.connect(self._on_match_mode_changed)

    mode_layout.addWidget(mode_label)
    mode_layout.addWidget(self.combo_mode)

    content_widget = VStack(
      sw_sandbox,
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
      QWidget(),
    )

    mode_container = QWidget()
    mode_container.setLayout(mode_layout)

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
        "Settings",
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
        button_type=ButtonType.DANGER,
      ),
      mode_container,
      sw_sandbox,
    )
    layout = QVBoxLayout(panel.container)
    layout.addWidget(content_widget)
    return panel

  def _on_sandbox_toggled(self, checked: bool, widget: Switch):
    self.ctx.settings.user.experimental_launch = checked
    self.ctx.settings.save(self.ctx.settings.user)

  def _on_match_mode_changed(self, index: int):
    new_mode = MatchMode.TIE if index == 0 else MatchMode.RANDOM
    self.ctx.settings.user.match_mode = new_mode
    self.ctx.settings.save(self.ctx.settings.system)
    logger.info(f"Match mode changed to: {new_mode.value}")

  def _kill_all_runners(self):
    running_accounts = WindowService.scan_cs2_windows(self.ctx.accounts(), values=True)
    for account in running_accounts:
      account.stop_account(self.ctx)

    asyncio.create_task(self.manager.into_state(states.Idle()))

  def _test_telegram(self):
    self.status_reset_service.send_farm_summary()

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
    self.log_text_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

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
      logger.debug(f"invalid layout: {e}")

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
