from typing import List, Tuple
from dataclasses import dataclass
from core.account.model import RunningAccount
from core.services.settings import FarmMode


@dataclass
class PartySchema:
  leader: RunningAccount
  members: List[RunningAccount]

  @property
  def farm_mode(self) -> FarmMode:
    """Вычисляемое поле на основе количества членов партии."""
    if len(self.members) == 1:
      return FarmMode.TWO_BY_TWO
    elif len(self.members) == 4:
      return FarmMode.FIVE_BY_FIVE
    else:
      raise ValueError(f"Неизвестный режим для {len(self.members)} членов")

  @property
  def all(self) -> List[RunningAccount]:
    return [self.leader, *self.members]


GameSchema = Tuple[PartySchema, PartySchema]
