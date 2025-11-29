from typing import Tuple, Union
from abc import ABC, abstractmethod
from enum import Enum

from core.services.gsi import Team


class Key(Enum):
  SHIFT = 0x10
  CTRL = 0x11
  ESC = 0x1B
  _0 = 0x30
  _1 = 0x31
  _2 = 0x32
  _3 = 0x33
  _4 = 0x34
  _5 = 0x35
  _6 = 0x36
  _7 = 0x37
  _8 = 0x38
  _9 = 0x39
  A = 0x41
  B = 0x42
  D = 0x44
  E = 0x45
  F = 0x46
  S = 0x53
  W = 0x57
  K = 0x4B
  L = 0x4C


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
