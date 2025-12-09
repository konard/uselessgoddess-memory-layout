from typing import Tuple, Union
from abc import ABC, abstractmethod
from core.keys import Key

from core.services.gsi import Team


class Context:
  def __init__(self, team, frame, targets, delta):
    self.team = team
    self.frame = frame
    self.targets = targets
    self.delta = delta


Step = Tuple[bool, Union[Team, None]]


class Action(ABC):
  @abstractmethod
  def execute(self, ctx: Context) -> Step:
    """Execute action. Returns True if action is completed immediately, False if still in progress"""
    pass

  @abstractmethod
  def release(self):
    """Release any held keys/buttons when action is completed"""
    pass
