import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.account.model import FarmStatus, RunningAccount
from core.logging import get_logger
from utils.name_generator import generate_preset_name

if TYPE_CHECKING:
  from core.context import Context
  from core.services.settings import FarmMode
  from states.types import GameSchema

logger = get_logger("sv.presets")

PRESETS_FILE = Path("data/presets.json")


@dataclass
class Preset:
  name: str

  accounts: list[str] = field(default_factory=list)
  has_error: bool = False

  def to_json(self) -> dict:
    return {
      "name": self.name,
      "accounts": self.accounts,
      "has_error": self.has_error,
    }

  @staticmethod
  def from_json(data: dict) -> "Preset":
    p = Preset(name=data["name"], accounts=data.get("accounts", []))
    p.has_error = data.get("has_error", False)
    return p

  @property
  def is_valid(self) -> bool:
    return len(self.accounts) in [4, 10]

  def get_party_schema(
    self, launched_accounts: list[RunningAccount]
  ) -> Optional["GameSchema"]:
    """
    Splits accounts into 2 parties based on specific indices.
    """
    from states.types import PartySchema

    if not self.is_valid:
      return None

    # Map launched accounts by login for easy lookup
    launched_map = {acc.login: acc for acc in launched_accounts}

    # Verify all preset accounts are present in launched_accounts
    if not all(login in launched_map for login in self.accounts):
      logger.warn("Not all preset accounts are launched")
      return None

    n = len(self.accounts)

    if n == 4:
      # Party A: 0 (Leader), 1
      leader_a = launched_map[self.accounts[0]]
      members_a = [launched_map[self.accounts[1]]]
      party_a = PartySchema(leader=leader_a, members=members_a)

      # Party B: 2 (Leader), 3
      leader_b = launched_map[self.accounts[2]]
      members_b = [launched_map[self.accounts[3]]]
      party_b = PartySchema(leader=leader_b, members=members_b)

      return (party_a, party_b)

    elif n == 10:
      # Party A: 0 (Leader), 1-4
      leader_a = launched_map[self.accounts[0]]
      members_a = [launched_map[acc] for acc in self.accounts[1:5]]
      party_a = PartySchema(leader=leader_a, members=members_a)

      # Party B: 5 (Leader), 6-9
      leader_b = launched_map[self.accounts[5]]
      members_b = [launched_map[acc] for acc in self.accounts[6:]]
      party_b = PartySchema(leader=leader_b, members=members_b)

      return (party_a, party_b)

    return None

  def get_status(self, ctx: "Context") -> FarmStatus:
    """
    Calculates aggregate status for the preset.
    Priority: NEED_TO_FARM > CAN_BE_LOOTED > FARMED > TRADED > BLOCKED
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
    if FarmStatus.TRADED in statuses:
      return FarmStatus.TRADED

    return FarmStatus.BLOCKED

  def swap_accounts(self, idx1: int, idx2: int):
    if 0 <= idx1 < len(self.accounts) and 0 <= idx2 < len(self.accounts):
      self.accounts[idx1], self.accounts[idx2] = (
        self.accounts[idx2],
        self.accounts[idx1],
      )


class PresetsService:
  def __init__(self):
    self.presets: dict[str, Preset] = {}
    self.load()

  def load(self):
    try:
      if Path(PRESETS_FILE).exists():
        with open(PRESETS_FILE, encoding="utf-8") as f:
          data = json.load(f)
          for name, schema_data in data.items():
            self.presets[name] = Preset.from_json(schema_data)
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

  def create_preset(self, name: str | None = None) -> bool:
    if not name:
      while True:
        name = generate_preset_name()
        if name not in self.presets:
          break

    if name in self.presets:
      return False
    self.presets[name] = Preset(name=name)
    self.save()
    return True

  def delete_preset(self, name: str):
    if name in self.presets:
      del self.presets[name]
      self.save()

  def get_preset(self, name: str) -> Preset | None:
    return self.presets.get(name)

  def is_account_used(self, login: str) -> bool:
    return any(login in schema.accounts for schema in self.presets.values())

  def get_preset_by_account(self, login: str) -> str | None:
    for schema in self.presets.values():
      if login in schema.accounts:
        return schema.name
    return None

  def add_account(self, preset_name: str, login: str) -> bool:
    # if self.is_account_used(login):
    #   logger.warn(f"Account {login} already in a preset")
    #   return False

    if preset_name in self.presets:
      schema = self.presets[preset_name]
      # Validation check
      if len(schema.accounts) >= 10:
        logger.warn("Preset full (max 10)")
        return False

      if login not in schema.accounts:
        schema.accounts.append(login)
        self.save()
        return True
    return False

  def remove_account(self, preset_name: str, login: str):
    if preset_name in self.presets and login in self.presets[preset_name].accounts:
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

  def update_preset_accounts(self, preset_name: str, new_accounts: list[str]):
    if preset_name in self.presets:
      self.presets[preset_name].accounts = new_accounts
      self.save()

  def mark_preset_error(self, name: str):
    if name in self.presets:
      self.presets[name].has_error = True
      self.save()

  def get_next_available_preset(self, ctx: "Context") -> Preset | None:
    for preset in self.presets.values():
      if (
        not preset.has_error
        and preset.is_valid
        and preset.get_status(ctx) == FarmStatus.NEED_TO_FARM
      ):
        return preset
    return None

  def find_preset_by_accounts(self, accounts: list[str]) -> Preset | None:
    """Find a preset that contains exactly the given accounts (order ignored)."""
    target_set = set(accounts)
    for preset in self.presets.values():
      if set(preset.accounts) == target_set:
        return preset
    return None

  def find_preset_by_game_schema(self, schema: "GameSchema") -> Preset | None:
    current_logins = []
    for party in schema:
      current_logins.extend([acc.login for acc in party.all])

    found_preset = self.find_preset_by_accounts(current_logins)
    if found_preset:
      if found_preset.accounts != current_logins:
        found_preset.accounts = current_logins
        self.save()
      return found_preset
    return None

  def get_schema_for_launched_accounts(
    self, launched_accounts: list[RunningAccount]
  ) -> Optional["GameSchema"]:
    if not launched_accounts:
      return None

    first_login = launched_accounts[0].login
    preset_name = self.get_preset_by_account(first_login)

    if preset_name:
      preset = self.get_preset(preset_name)
      if preset:
        return preset.get_party_schema(launched_accounts)

    return None

  def get_all_presets(self) -> list[Preset]:
    return list(self.presets.values())

  def find_similar_preset_missing_account(
    self, launched_logins: list[str], ctx: "Context"
  ) -> str | None:
    from core.services.settings import FarmMode

    farm_mode = ctx.settings.system.farm_mode
    required_count = 4 if farm_mode == FarmMode.TWO_BY_TWO else 10
    threshold = 3 if farm_mode == FarmMode.TWO_BY_TWO else 9

    launched_set = set(launched_logins)

    for preset in self.presets.values():
      if preset.has_error or not preset.is_valid:
        continue

      if len(preset.accounts) != required_count:
        continue

      preset_set = set(preset.accounts)
      intersection = preset_set & launched_set
      missing = preset_set - launched_set

      if len(intersection) == threshold and len(missing) == 1:
        missing_login = list(missing)[0]
        if missing_login in ctx.account.accounts:
          account = ctx.account.accounts[missing_login]
          if account.lock.status == FarmStatus.NEED_TO_FARM:
            logger.info(
              f"Found similar preset '{preset.name}' with {threshold}/{required_count}"
              + f"accounts, missing: {missing_login}"
            )
            return missing_login

    return None
