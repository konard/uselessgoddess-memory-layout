import time
import threading
import queue
import random
import enum
import traceback
from typing import Optional, Dict, List
from dataclasses import dataclass

from core.account import Account
from core.context import Context
from core.services.gsi.models import GameState, Team, RoundPhase, Map
from core.services import WindowService, CS2Controller
from core.services.settings import MatchMode
from core.services.capture import Region
from core.keys import Key
from core.logging import get_logger
from states.match.impl.walk import scancode

from .impl import infer_path, config, Path

logger = get_logger("match.worker")


# internal mode settings with extra dev flags
@dataclass
class ModeSettings:
  teams: List[Team] = None
  prefer_plant: bool = False
  max_round: int = 8  # todo allow non-tie


DEV_MODE = ModeSettings(
  teams=[Team.T, Team.CT],
  prefer_plant=False,
)


class State(enum.IntEnum):
  Prepare = 0
  Round = 1
  Stop = 2


@dataclass
class PlayerEntry:
  team: Team
  account: Account
  bomb: bool
  phase: RoundPhase
  win_cs_title: str


def score_from(map: Map):
  return {
    Team.T: map.team_t.score,
    Team.CT: map.team_ct.score,
  }


class MatchWorker(threading.Thread):
  def __init__(self, ctx: Context, accounts: list):
    super().__init__(name="MatchWorker", daemon=True)
    self.ctx = ctx
    self.accounts = accounts
    self.lifetime = 0
    self.mode = DEV_MODE
    self.running = True
    self.ingame = False
    self.disconnect = False
    self.status = "Initializing..."

    self.path: Path = None
    self.players: Dict[str, PlayerEntry] = {}
    self.score = {Team.CT: 0, Team.T: 0}
    self.round = -1
    self.state = State.Prepare
    self._event_queue = queue.Queue(maxsize=12)

    # TODO: infer max round from 2x2 or 5x5
    if self.ctx.su.match_mode == MatchMode.TIE:
      self.mode.max_round = 8
    else:
      self.mode.max_round = 999

  def run(self):
    logger.info("Worker started")
    last_time = time.perf_counter()

    while self.running:
      curr = time.perf_counter()

      try:
        event: GameState = self._event_queue.get_nowait()
        self.process_state(event)
      except queue.Empty:
        pass

      if self.all_ready() and self.player is not None:
        if self.state == State.Prepare:
          # anti afk system
          self.coco_jambo(self.player.bomb)
          self.state = State.Round
          WindowService.focus_window(self.player.win_cs_title)
        else:
          self.status = f"Round {self.round}: {self.player.account.login} ({self.state.name})"

          x, y = self.player.account.posX, self.player.account.posY
          w, h = self.ctx.su.win_w, self.ctx.su.win_h
          frame = self.ctx.screen.capture(Region(x, y, w, h))
          if frame is not None:
            if self.state != State.Round:
              continue

            stop, team = self.path.step(
              frame,
              self.ctx.ai,
              curr - last_time,
            )

            if stop:
              self.state = State.Stop
            elif team is not None:
              next_players = [
                player
                for player in self.filter_team(team)
                if player.account.steam_id != self.player.account.steam_id
              ]
              if not next_players:
                logger.error("LESS THAN 2 PLAYERS IN TEAM!")
              else:
                self.player = random.choice(next_players)
              WindowService.focus_window(self.player.win_cs_title)
      last_time = curr
      time.sleep(0.001)

    logger.debug(f"Worker exit with status: {self.status}")

  def exit(self):
    self.running = False
    self.status = "Exiting..."

  def active_players(self):
    return list(self.players.values())

  def all_ready(self):
    return (
      len(self.accounts) > 0
      and len(self.active_players()) == len(self.accounts)
      and all([p.phase == RoundPhase.LIVE for p in self.active_players()])
    )

  def filter_team(self, team: Team) -> List[PlayerEntry]:
    return list(p for k, p in self.players.items() if p.team == team)

  def on_game_state(self, event: GameState):
    try:
      self._event_queue.put_nowait(event)
    except queue.Full:
      try:
        self._event_queue.get_nowait()
        self._event_queue.put_nowait(event)
      except queue.Empty:
        pass

  def process_state(self, event: GameState):
    map, round, player = event.map, event.round, event.player

    # kill after 10 minute of nothing
    if self.lifetime > 10 * 60:
      self.running = False
    else:
      logger.trace(f"lifetime: {self.lifetime}")

    probe_score = score_from(map)
    # avoid zero after match
    if sum(probe_score.values()) > sum(self.score.values()):
      self.score = probe_score

    contains_c4 = any(weapon.type == "C4" for weapon in player.weapons)

    for account in self.accounts:
      if str(player.steam_id) == str(account.steam_id):
        if player.team != Team.UNDEFINED:
          self.players[player.steam_id] = PlayerEntry(
            team=player.team,
            account=account,
            phase=round.phase,
            bomb=contains_c4,
            win_cs_title=f"[{account.login}] # CS",  # TODO: from account
          )
        elif player.steam_id in self.players:
          # Remove player from active players if team is undefined
          del self.players[player.steam_id]

    if map.round != self.round and self.all_ready():
      self.round = map.round
      self.disconnect = False
      logger.debug(f"start new round {self.round}")

      self.score = score_from(map)
      self.start_round(map.name, map.mode, self.score)
      self.lifetime = 0.0

    if map.round != self.round and self.disconnect:
      self.coco_jambo(False)

    active_players = len(self.active_players())
    if self.ingame and active_players == 0:
      self.running = False
    else:
      self.status_text = f"Waiting {active_players}/{len(self.accounts)}..."

    # disconnect
    if self.running and self.ingame and active_players != len(self.accounts):
      self.disconnect = True
      self.coco_jambo(False)

  def start_round(self, map_name: str, mode: str, score: dict):
    maxround = self.mode.max_round - 2
    reach_maxround = score[Team.T] >= maxround or score[Team.CT] >= maxround

    if abs(score[Team.T] - score[Team.CT]) > 5 or reach_maxround:
      team = Team.T if score[Team.T] < score[Team.CT] else Team.CT
    else:
      team = random.choice(self.mode.teams)

    debug = f"team={team.label()}, map={map_name}, mode={mode}"
    logger.debug(f"starting round with {debug}")

    mates = sorted(self.filter_team(team), key=lambda p: not p.bomb)

    if self.mode.prefer_plant:
      self.player = mates[0]
    else:
      self.player = random.choice(mates)

    self.path = infer_path(
      map_name, mode, team, self.player.bomb, reach_maxround
    )
    if self.path is None:
      logger.error(f"path not found for {debug}")
      self.exit()

    self.state = State.Prepare
    self.ingame = True

  def coco_jambo(self, bomb: bool):
    for player in self.active_players():
      WindowService.focus_window(player.win_cs_title)
      time.sleep(0.2)
      CS2Controller.press_button(Key.F.value, sleep=0.5)
      CS2Controller.press_button(Key.CTRL.value, sleep=0.5)
      CS2Controller.press_button(ord("2"))
      if player.team == Team.CT:
        if bomb:
          CS2Controller.press_button(scancode(35).value)
        if random.random() < 0.50:
          CS2Controller.press_button(scancode(37).value)
      CS2Controller.press_button(Key.F3.value, sleep=0.5)

  def stop(self):
    self.exit()
    self.join()
