from dataclasses import dataclass, field
from typing import List

@dataclass
class Message:
    """base message class"""
    pass

@dataclass
class StartFarming(Message):
    logins: List[str] = field(default_factory=list)

@dataclass
class StopFarming(Message):
    pass
