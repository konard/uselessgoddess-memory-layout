import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from pathlib import Path

from core.logging import get_logger
from core.account.model import FarmStatus

if TYPE_CHECKING:
  from core.context import Context

logger = get_logger("sv.presets")

PRESETS_FILE = "presets.json"


@dataclass
class PartyPreset:
  leader: str
  members: List[str]

  def to_json(self) -> dict:
    return {"leader": self.leader, "members": self.members}

  @staticmethod
  def from_json(data: dict) -> "PartyPreset":
    return PartyPreset(
      leader=data.get("leader", ""), members=data.get("members", [])
    )

  @property
  def all(self) -> List[str]:
    return [self.leader] + self.members


@dataclass
class GameSchema:
  name: str
  # accounts is no longer just a flat list for storage, but we can maintain backward compatibility
  # or migrate. Let's stick to flat list for simple storage but rely on order.
  # New logic:
  # 2x2 mode (4 accounts):
  #   accounts[0] -> Leader Party A
  #   accounts[1] -> Member Party A
  #   accounts[2] -> Leader Party B
  #   accounts[3] -> Member Party B
  # 5x5 mode (10 accounts):
  #   accounts[0] -> Leader Party A
  #   accounts[1..4] -> Members Party A
  #   accounts[5] -> Leader Party B
  #   accounts[6..9] -> Members Party B

  accounts: List[str] = field(default_factory=list)

  def to_json(self) -> dict:
    return {"name": self.name, "accounts": self.accounts}

  @staticmethod
  def from_json(data: dict) -> "GameSchema":
    return GameSchema(name=data["name"], accounts=data.get("accounts", []))

  @property
  def is_valid(self) -> bool:
    return len(self.accounts) in [4, 10]

  def get_party_schema(self) -> List[PartyPreset]:
    """
    Splits accounts into 2 parties based on specific indices.
    """
    if not self.is_valid:
      return []

    n = len(self.accounts)

    if n == 4:
      # Party A: 0 (Leader), 1
      party_a = PartyPreset(leader=self.accounts[0], members=[self.accounts[1]])
      # Party B: 2 (Leader), 3
      party_b = PartyPreset(leader=self.accounts[2], members=[self.accounts[3]])
      return [party_a, party_b]

    elif n == 10:
      # Party A: 0 (Leader), 1-4
      party_a = PartyPreset(leader=self.accounts[0], members=self.accounts[1:5])
      # Party B: 5 (Leader), 6-9
      party_b = PartyPreset(leader=self.accounts[5], members=self.accounts[6:])
      return [party_a, party_b]

    return []

  def get_status(self, ctx: "Context") -> FarmStatus:
    """
    Calculates aggregate status for the preset.
    Priority: NEED_TO_FARM > CAN_BE_LOOTED > FARMED > TRADED
    """
    statuses = set()
    for login in self.accounts:
      acc = ctx.account.accounts.get(login)
      if acc:
        statuses.add(acc.lock.status or FarmStatus.NEED_TO_FARM)

    if FarmStatus.NEED_TO_FARM in statuses:
      return FarmStatus.NEED_TO_FARM
    if FarmStatus.CAN_BE_LOOTED in statuses:
      return FarmStatus.CAN_BE_LOOTED
    if FarmStatus.FARMED in statuses:
      return FarmStatus.FARMED

    return FarmStatus.TRADED

  def swap_accounts(self, idx1: int, idx2: int):
    if 0 <= idx1 < len(self.accounts) and 0 <= idx2 < len(self.accounts):
      self.accounts[idx1], self.accounts[idx2] = (
        self.accounts[idx2],
        self.accounts[idx1],
      )


class PresetsService:
  def __init__(self):
    self.presets: Dict[str, GameSchema] = {}
    self.load()

  def load(self):
    try:
      if Path(PRESETS_FILE).exists():
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
          for name, schema_data in data.items():
            self.presets[name] = GameSchema.from_json(schema_data)
        logger.info(f"Loaded {len(self.presets)} presets")
    except Exception as e:
      logger.error(f"Failed to load presets: {e}")

  def save(self):
    try:
      data = {name: schema.to_json() for name, schema in self.presets.items()}
      with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    except Exception as e:
      logger.error(f"Failed to save presets: {e}")

  def create_preset(self, name: str) -> bool:
    if name in self.presets:
      return False
    self.presets[name] = GameSchema(name=name)
    self.save()
    return True

  def delete_preset(self, name: str):
    if name in self.presets:
      del self.presets[name]
      self.save()

  def get_preset(self, name: str) -> Optional[GameSchema]:
    return self.presets.get(name)

  def is_account_used(self, login: str) -> bool:
    for schema in self.presets.values():
      if login in schema.accounts:
        return True
    return False

  def get_preset_by_account(self, login: str) -> Optional[str]:
    for schema in self.presets.values():
      if login in schema.accounts:
        return schema.name
    return None

  def add_account(self, preset_name: str, login: str) -> bool:
    if self.is_account_used(login):
      logger.warning(f"Account {login} already in a preset")
      return False

    if preset_name in self.presets:
      schema = self.presets[preset_name]
      # Validation check
      if len(schema.accounts) >= 10:
        logger.warning("Preset full (max 10)")
        return False

      if login not in schema.accounts:
        schema.accounts.append(login)
        self.save()
        return True
    return False

  def remove_account(self, preset_name: str, login: str):
    if preset_name in self.presets:
      if login in self.presets[preset_name].accounts:
        self.presets[preset_name].accounts.remove(login)
        self.save()

  def move_account_up(self, preset_name: str, index: int):
    if preset_name in self.presets:
      schema = self.presets[preset_name]
      if index > 0 and index < len(schema.accounts):
        schema.swap_accounts(index, index - 1)
        self.save()

  def move_account_down(self, preset_name: str, index: int):
    if preset_name in self.presets:
      schema = self.presets[preset_name]
      if index >= 0 and index < len(schema.accounts) - 1:
        schema.swap_accounts(index, index + 1)
        self.save()

  def update_preset_accounts(self, preset_name: str, new_accounts: List[str]):
    if preset_name in self.presets:
      self.presets[preset_name].accounts = new_accounts
      self.save()

  def get_all_presets(self) -> List[GameSchema]:
    return list(self.presets.values())
