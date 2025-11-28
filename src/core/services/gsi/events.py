from dataclasses import dataclass
from .models import GameState, Team, RoundPhase, MapPhase


@dataclass
class GSIEvent:
  state: GameState


@dataclass
class RoundEndEvent(GSIEvent):
  winner: Team
  reason: str = (
    ""  # Often not provided clearly by simple GSI, but implies win condition
  )


@dataclass
class RoundStartEvent(GSIEvent):
  round_number: int


@dataclass
class MapChangeEvent(GSIEvent):
  old_map: str
  new_map: str
  mode: str


@dataclass
class MatchEndEvent(GSIEvent):
  winner: Team
  score_ct: int
  score_t: int
