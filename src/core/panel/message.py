from dataclasses import dataclass, field


@dataclass
class Message:
  """base message class"""


@dataclass
class StartFarming(Message):
  logins: list[str] = field(default_factory=list)


@dataclass
class StopFarming(Message):
  pass
