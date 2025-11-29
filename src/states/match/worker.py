import time
import threading
import queue
import traceback
from typing import Optional, Dict, List
from dataclasses import dataclass

from core.context import Context
from core.services.gsi.models import GameState, Team, RoundPhase
from core.services import WindowService
from core.services.capture import Region
from core.logging import get_logger

from .impl import infer_path, config, Path

logger = get_logger("match.worker")


@dataclass
class PlayerEntry:
  steam_id: str
  team: Team
  phase: RoundPhase
  bomb: bool


class MatchWorker(threading.Thread):
  def __init__(self, ctx: Context, accounts: list):
    super().__init__(name="MatchWorker", daemon=True)
    self.ctx = ctx
    self.accounts = accounts

    self.running = False
    self.paused = False
    self.status = "Idle"

    # State Queue (как в оригинале)
    self.state_queue = queue.Queue(maxsize=12)

    # Match State
    self.current_path: Optional[Path] = None
    self.players: Dict[str, PlayerEntry] = {}
    self.round_number = -1
    self.round_active = False

    # Current active player index (for rotation if needed)
    self.current_idx = 0

  def run(self):
    logger.info("Worker started")
    self.running = True
    last_time = time.perf_counter()

    while self.running:
      # 1. Process GSI Queue
      try:
        state = self.state_queue.get_nowait()
        self._process_gsi_event(state)
      except queue.Empty:
        pass

      # 2. Physics / AI Loop
      curr_time = time.perf_counter()
      delta = curr_time - last_time
      last_time = curr_time

      if not self.round_active or self.paused:
        time.sleep(0.01)
        continue

      try:
        self._process_frame(delta)
      except Exception:
        logger.error(traceback.format_exc())
        time.sleep(1.0)

  def on_game_state(self, state: GameState):
    try:
      self.state_queue.put_nowait(state)
    except queue.Full:
      try:
        self.state_queue.get_nowait()
        self.state_queue.put_nowait(state)
      except queue.Empty:
        pass

  def _process_gsi_event(self, state: GameState):
    player = state.player
    steam_id = state.provider.steamid
    if not steam_id or steam_id == "0":
      steam_id = player.steam_id

    # 1. Update Player Registry
    # Проверяем, есть ли этот игрок в наших аккаунтах
    is_our_account = any(
      str(acc.steam_id) == str(steam_id) for acc in self.accounts
    )

    if is_our_account:
      has_bomb = any(w.type.name == "C4" for w in player.weapons)

      if player.team != Team.UNDEFINED:
        self.players[steam_id] = PlayerEntry(
          steam_id=steam_id,
          team=player.team,
          phase=state.round.phase,
          bomb=has_bomb,
        )
      elif steam_id in self.players:
        # Игрок вышел или undefined
        del self.players[steam_id]

    # 2. Check Round Change
    # Логика: если номер раунда сменился И все игроки готовы (LIVE)
    if state.map.round != self.round_number and self._all_ready():
      logger.info(f"New round detected: {state.map.round}")
      self.round_number = state.map.round
      self._start_round(state.map.name, state.map.mode)

    # 3. Update Status Info
    ready_count = len(
      [p for p in self.players.values() if p.phase == RoundPhase.LIVE]
    )
    if not self.round_active:
      self.status = f"Waiting... ({ready_count}/{len(self.accounts)} Ready)"

  def _all_ready(self) -> bool:
    """Все ли аккаунты зашли за команду и находятся в фазе LIVE?"""
    if not self.accounts:
      return False

    # В оригинале проверялось: len(active) == len(accounts) and all(LIVE)
    if len(self.players) < len(self.accounts):
      return False

    return all(p.phase == RoundPhase.LIVE for p in self.players.values())

  def _start_round(self, map_name: str, mode: str):
    # Выбираем команду для логики (берем команду первого попавшегося нашего игрока)
    # В идеале нужно смотреть score difference, как в оригинале
    my_team = Team.CT
    if self.players:
      my_team = list(self.players.values())[0].team

    logger.info(f"Starting round logic for {map_name} as {my_team}")

    # Генерируем путь
    self.current_path = infer_path(
      map_name, my_team, bomb=False
    )  # Bomb check logic todo
    self.round_active = True
    self.status = "Round Live"

  # --- Physics / AI ---

  def _process_frame(self, delta: float):
    if not self.accounts:
      return

    # TODO: Ротация аккаунтов? Пока берем 0-й
    acc = self.accounts[self.current_idx]

    win = WindowService.get_window_info(acc.win_cs_title)
    if not win:
      return

    wx, wy = win["posX"], win["posY"]
    WIN_W, WIN_H = self.ctx.su.win_w, self.ctx.su.win_h

    cx = wx + (WIN_W - config.screenshot_width) // 2
    cy = wy + (WIN_H - config.screenshot_height) // 2

    region = Region(cx, cy, config.screenshot_width, config.screenshot_height)
    frame = self.ctx.screen.capture(region)
    if frame is None:
      return

    targets = self.ctx.ai.infer(frame)

    if self.current_path:
      self.status = f"Pathing ({acc.login})"
      finished, new_team = self.current_path.step(self.ctx, targets, delta)
      if finished:
        self.current_path = None
        self.status = "Path Finished"

    time.sleep(0.001)

  def stop(self):
    self.running = False
    self.join()
