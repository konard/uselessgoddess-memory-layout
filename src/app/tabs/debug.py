import time

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
  QFrame,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QProgressBar,
  QScrollArea,
  QVBoxLayout,
  QWidget,
)

from core.context import Context
from core.services.gsi.models import GameState, Team
from ui.theme import CURRENT_THEME
from ui.widgets import Label, LabelType, TitledPanel


class SignalBridge(QObject):
  gsi_updated = pyqtSignal(object)


class StatCard(QFrame):
  def __init__(self, title, value, parent=None):
    super().__init__(parent)
    self.setStyleSheet(f"""
            QFrame {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(2)

    lbl_title = QLabel(title)
    lbl_title.setStyleSheet(f"color: {CURRENT_THEME.SECONDARY_TEXT}; font-size: 10px;")
    lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

    self.lbl_value = QLabel(str(value))
    self.lbl_value.setStyleSheet(
      f"color: {CURRENT_THEME.PRIMARY_TEXT}; font-weight: bold; font-size: 14px;"
    )
    self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(lbl_title)
    layout.addWidget(self.lbl_value)

  def set_value(self, val):
    self.lbl_value.setText(str(val))


class MatchHeaderWidget(QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)
    self._setup_ui()

  def _setup_ui(self):
    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)

    # --- Info Panel ---
    self.info_panel = TitledPanel("Match State")
    info_layout = QHBoxLayout(self.info_panel.container)

    self.lbl_map = Label("Waiting for GSI...", LabelType.HEADER)
    self.lbl_round = Label("Round: -")
    self.lbl_phase = Label("Phase: -")

    info_layout.addWidget(self.lbl_map)
    info_layout.addStretch()
    info_layout.addWidget(self.lbl_round)
    info_layout.addWidget(self.lbl_phase)

    layout.addWidget(self.info_panel, stretch=2)

    # --- Scoreboard ---
    self.score_panel = TitledPanel("Score")
    score_layout = QHBoxLayout(self.score_panel.container)

    self.lbl_ct = QLabel("0")
    self.lbl_ct.setStyleSheet(
      f"font-size: 24px; font-weight: bold; color: {CURRENT_THEME.ACCENT_BLUE};"
    )

    self.lbl_t = QLabel("0")
    self.lbl_t.setStyleSheet(
      f"font-size: 24px; font-weight: bold; color: {CURRENT_THEME.ACCENT_YELLOW};"
    )

    score_layout.addStretch()
    score_layout.addWidget(self.lbl_ct)
    score_layout.addWidget(Label(":"))
    score_layout.addWidget(self.lbl_t)
    score_layout.addStretch()

    layout.addWidget(self.score_panel, stretch=1)

  def update_global(self, state: GameState):
    self.lbl_map.set(f"{state.map.name} ({state.map.mode})")
    self.lbl_round.set(f"Round: {state.map.round}")
    self.lbl_phase.set(f"Phase: {state.round.phase}")

    self.lbl_ct.setText(str(state.map.team_ct.score))
    self.lbl_t.setText(str(state.map.team_t.score))


class PlayerGSIWidget(QWidget):
  def __init__(self, steam_id: str, login: str, parent=None):
    super().__init__(parent)
    self.steam_id = steam_id
    self.login = login
    self.last_update_ts = time.time()
    self._setup_ui()

  def _setup_ui(self):
    self.panel = TitledPanel(f"{self.login}")
    self.container_layout = QVBoxLayout(self)
    self.container_layout.setContentsMargins(0, 0, 0, 0)
    self.container_layout.addWidget(self.panel)

    layout = QVBoxLayout(self.panel.container)
    layout.setSpacing(8)

    # --- Name & Weapon (Compact Row) ---
    top_row = QHBoxLayout()
    self.lbl_ingame_name = Label("...", LabelType.PRIMARY)
    self.lbl_weapon = Label("-", LabelType.SECONDARY)

    top_row.addWidget(self.lbl_ingame_name)
    top_row.addStretch()
    top_row.addWidget(self.lbl_weapon)
    layout.addLayout(top_row)

    # --- Bars ---
    bars_grid = QGridLayout()
    bars_grid.setContentsMargins(0, 0, 0, 0)

    self.bar_health = self._create_bar(CURRENT_THEME.ACCENT_GREEN, "HP: %v")
    self.bar_armor = self._create_bar(CURRENT_THEME.ACCENT_BLUE, "AP: %v")
    self.bar_ammo = self._create_bar(CURRENT_THEME.ACCENT_ORANGE, "Ammo: %v")

    bars_grid.addWidget(self.bar_health, 0, 0)
    bars_grid.addWidget(self.bar_armor, 0, 1)
    bars_grid.addWidget(self.bar_ammo, 1, 0, 1, 2)

    layout.addLayout(bars_grid)

    # --- Stats ---
    stats_layout = QHBoxLayout()
    self.card_k = StatCard("K", 0)
    self.card_d = StatCard("D", 0)
    self.card_a = StatCard("A", 0)
    self.card_money = StatCard("$", 0)

    stats_layout.addWidget(self.card_k)
    stats_layout.addWidget(self.card_d)
    stats_layout.addWidget(self.card_a)
    stats_layout.addWidget(self.card_money)

    layout.addLayout(stats_layout)

  def _create_bar(self, color, fmt):
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setFixedHeight(12)
    bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {CURRENT_THEME.BORDER};
                border-radius: 3px;
                background-color: {CURRENT_THEME.BACKGROUND};
                text-align: center;
                color: {CURRENT_THEME.PRIMARY_TEXT};
                font-size: 9px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)
    bar.setFormat(fmt)
    return bar

  def update_state(self, state: GameState):
    self.last_update_ts = time.time()
    player = state.player

    if player:
      color = CURRENT_THEME.PRIMARY_TEXT
      if player.team == Team.CT:
        color = CURRENT_THEME.ACCENT_BLUE
      elif player.team == Team.T:
        color = CURRENT_THEME.ACCENT_YELLOW

      self.lbl_ingame_name.setText(f"{player.name}")
      self.lbl_ingame_name.setStyleSheet(f"font-weight: bold; color: {color};")

      self.bar_health.setValue(player.state.health)
      self.bar_armor.setValue(player.state.armor)

      self.card_k.set_value(player.match_stats.kills)
      self.card_d.set_value(player.match_stats.deaths)
      self.card_a.set_value(player.match_stats.assists)
      self.card_money.set_value(player.state.money)

      active = player.active_weapon
      if active:
        self.lbl_weapon.set(f"{active.name}")
        self.bar_ammo.setRange(0, active.ammo_clip_max)
        self.bar_ammo.setValue(active.ammo_clip)
        self.bar_ammo.setFormat(f"{active.ammo_clip} / {active.ammo_reserve}")
      else:
        self.lbl_weapon.set("Holstered")
        self.bar_ammo.setValue(0)
        self.bar_ammo.setFormat("-")


class GSITab(QWidget):
  TIMEOUT_SECONDS = 30.0  # TODO: depends on heartbeat

  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx

    self.active_widgets: dict[str, PlayerGSIWidget] = {}
    self.sorted_logins: list[str] = []

    self.bridge = SignalBridge()
    self.bridge.gsi_updated.connect(self._on_gsi_packet)
    self.ctx.gsi.listen_raw(self.bridge.gsi_updated.emit)

    self._setup_ui()

    self.cleanup_timer = QTimer(self)
    self.cleanup_timer.timeout.connect(self._prune_stale_sessions)
    self.cleanup_timer.start(1000)

  def _setup_ui(self):
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(10)

    # Global Match Header
    self.header = MatchHeaderWidget()
    main_layout.addWidget(self.header)

    # Players Scroll Area
    self.scroll_area = QScrollArea()
    self.scroll_area.setWidgetResizable(True)
    self.scroll_area.setStyleSheet("""
            QScrollArea {{ border: none; background-color: transparent; }}
            QWidget {{ background-color: transparent; }}
        """)

    self.container = QWidget()
    self.container_layout = QVBoxLayout(self.container)
    self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    self.container_layout.setSpacing(10)

    self.scroll_area.setWidget(self.container)
    main_layout.addWidget(self.scroll_area)

    # Status Label
    self.lbl_status = Label("Waiting for players...", LabelType.SECONDARY)
    self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    main_layout.addWidget(self.lbl_status)

  def _get_login_by_steamid(self, steam_id: str) -> str:
    """Ищет логин аккаунта по steam_id в локальной базе."""
    accounts = self.ctx.account.accounts
    for login, acc in accounts.items():
      if str(acc.steam_id) == str(steam_id):
        return login
    return f"Unknown ({steam_id})"

  @pyqtSlot(object)
  def _on_gsi_packet(self, state: GameState):
    self.header.update_global(state)

    sid = state.provider.steamid
    if not sid or sid == "0":
      sid = state.player.steam_id
    if not sid:
      return

    if sid not in self.active_widgets:
      self._add_new_widget(sid)

    self.active_widgets[sid].update_state(state)

  def _add_new_widget(self, steam_id: str):
    login = self._get_login_by_steamid(steam_id)

    widget = PlayerGSIWidget(steam_id, login)
    self.active_widgets[steam_id] = widget

    existing_widgets_data = []
    for i in range(self.container_layout.count()):
      w = self.container_layout.itemAt(i).widget()
      if isinstance(w, PlayerGSIWidget):
        existing_widgets_data.append(w)

    insert_index = len(existing_widgets_data)
    for i, w in enumerate(existing_widgets_data):
      if login.lower() < w.login.lower():
        insert_index = i
        break

    self.container_layout.insertWidget(insert_index, widget)
    self.lbl_status.set(f"Active sessions: {len(self.active_widgets)}")

  def _prune_stale_sessions(self):
    now = time.time()
    to_remove = []

    for sid, widget in self.active_widgets.items():
      if now - widget.last_update_ts > self.TIMEOUT_SECONDS:
        to_remove.append(sid)

    for sid in to_remove:
      widget = self.active_widgets.pop(sid)
      self.container_layout.removeWidget(widget)
      widget.deleteLater()

    if to_remove:
      self.lbl_status.set(f"Active sessions: {len(self.active_widgets)}")
