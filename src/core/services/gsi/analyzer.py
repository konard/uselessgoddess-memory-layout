from typing import Optional

from .events import (
  GSIEvent,
  MapChangeEvent,
  MatchEndEvent,
  RoundEndEvent,
  RoundStartEvent,
)
from .models import GameState, MapPhase, RoundPhase, Team


class GSIAnalyzer:
  def __init__(self):
    self._prev: GameState | None = None

  def analyze(self, current: GameState) -> list[GSIEvent]:
    events = []
    if self._prev is None:
      self._prev = current
      return events

    if self._prev.map.name != current.map.name:
      events.append(
        MapChangeEvent(
          state=current,
          old_map=self._prev.map.name,
          new_map=current.map.name,
          mode=current.map.mode,
        )
      )

    if (
      self._prev.round.phase == RoundPhase.LIVE and current.round.phase == RoundPhase.OVER
    ):
      events.append(RoundEndEvent(state=current, winner=current.round.win_team))

    if (
      self._prev.round.phase == RoundPhase.OVER
      and current.round.phase == RoundPhase.FREEZETIME
    ):
      events.append(RoundStartEvent(state=current, round_number=current.map.round))

    if self._prev.map.phase == MapPhase.LIVE and current.map.phase == MapPhase.GAME_OVER:
      ct_score = current.map.team_ct.score
      t_score = current.map.team_t.score
      winner = Team.CT if ct_score > t_score else Team.T
      if ct_score == t_score:
        winner = Team.UNDEFINED

      events.append(
        MatchEndEvent(state=current, winner=winner, score_ct=ct_score, score_t=t_score)
      )

    self._prev = current
    return events
