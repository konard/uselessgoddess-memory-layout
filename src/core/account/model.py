from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from enum import Enum

import core
from core.logging import get_logger
from .lock import AccountsLock

from constants import SANDBOX_PATH

logger = get_logger("account.model")


class FarmStatus(str, Enum):
  NEED_TO_FARM = "need_to_farm"
  CAN_BE_LOOTED = "can_be_looted"
  FARMED = "farmed"
  TRADED = "traded"
  BLOCKED = "blocked"


status_map = {
  FarmStatus.NEED_TO_FARM: FarmStatus.CAN_BE_LOOTED,
  FarmStatus.CAN_BE_LOOTED: FarmStatus.FARMED,
  FarmStatus.FARMED: FarmStatus.TRADED,
  FarmStatus.TRADED: FarmStatus.NEED_TO_FARM,
}


class Metadata(dict):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setdefault("lvl", 0)
    self.setdefault("xp", 0)
    self.setdefault("invite", "")
    self.setdefault("status", FarmStatus.NEED_TO_FARM)
    self.setdefault("vac_banned", False)
    self.setdefault("refresh_token", "")


@dataclass(slots=True)
class AccountMetadata:
  _data: Dict[str, Any] = field(default_factory=Metadata, init=False)
  _lock: AccountsLock | None = field(init=False, default=None)
  _login: str = field(init=False, default="")

  def update_from_lock(self, login: str, lock: AccountsLock) -> None:
    self._lock = lock
    self._login = login

    info = lock.get_account_info(login) or {}

    self._data.update(info)
    if len(info) < len(self._data):
      self.save_to_lock()

  def save_to_lock(self) -> None:
    if self._lock and self._login:
      self._lock.set_account_info(self._login, **self._data)

  @property
  def lvl(self) -> int | None:
    return self._data.get("lvl")

  @lvl.setter
  def lvl(self, value: int) -> None:
    updates = {}
    current_lvl = self._data.get("lvl", 0)
    if value > current_lvl and current_lvl != 0:
      self._data["status"] = FarmStatus.CAN_BE_LOOTED
      updates["status"] = FarmStatus.CAN_BE_LOOTED

    self._data["lvl"] = value
    updates["lvl"] = value

    if self._lock:
      self._lock.set_account_info(self._login, **updates)

  @property
  def xp(self) -> int | None:
    return self._data.get("xp")

  @property
  def vac_banned(self) -> bool | None:
    return self._data.get("vac_banned")

  @vac_banned.setter
  def vac_banned(self, value: bool) -> None:
    self._data["vac_banned"] = value
    if self._lock:
      self._lock.set_field(self._login, "vac_banned", value)

  @property
  def refresh_token(self) -> str | None:
    return self._data.get("refresh_token")

  @refresh_token.setter
  def refresh_token(self, value: str) -> None:
    self._data["refresh_token"] = value
    if self._lock:
      self._lock.set_field(self._login, "refresh_token", value)

  @xp.setter
  def xp(self, value: int) -> None:
    updates = {}
    current_xp = self._data.get("xp", 0)
    if value < current_xp and current_xp != 0:
      self._data["status"] = FarmStatus.CAN_BE_LOOTED
      updates["status"] = FarmStatus.CAN_BE_LOOTED

    self._data["xp"] = value
    updates["xp"] = value

    if self._lock:
      self._lock.set_account_info(self._login, **updates)

  @property
  def invite(self) -> str | None:
    return self._data.get("invite")

  @invite.setter
  def invite(self, value: str) -> None:
    self._data["invite"] = value
    if self._lock:
      self._lock.set_field(self._login, "invite", value)

  @property
  def status(self) -> FarmStatus | None:
    return self._data.get("status")

  @status.setter
  def status(self, value: FarmStatus) -> None:
    self._data["status"] = value

    if self._lock:
      self._lock.set_field(self._login, "status", value)

  def get(self, field_name: str, default: Any = None) -> Any:
    return self._data.get(field_name, default)

  def set(self, field_name: str, value: Any) -> None:
    self._data[field_name] = value
    if self._lock:
      self._lock.set_field(self._login, field_name, value)


@dataclass(slots=True)
class Account:
  login: str
  password: str
  shared_secret: str
  identity_secret: str | None
  steam_id: str

  lock: AccountMetadata = field(default_factory=AccountMetadata, init=False)

  @staticmethod
  def from_json(data: dict) -> "Account":
    return Account(
      login=data["login"],
      password=data["password"],
      shared_secret=data["shared_secret"],
      identity_secret=data.get("identity_secret", None),
      steam_id=data["steam_id"],
    )

  def to_json(self) -> dict:
    return {
      "login": self.login,
      "password": self.password,
      "shared_secret": self.shared_secret,
      "identity_secret": self.identity_secret,
      "steam_id": self.steam_id,
    }

  def update_from_lock(self, accounts_lock: "AccountsLock") -> None:
    """
    Обновить метаданные аккаунта из lock.
    """
    self.lock._lock = accounts_lock
    self.lock.update_from_lock(self.login, accounts_lock)


@dataclass(slots=True)
class RunningAccount(Account):
  posX: int = 0
  posY: int = 0
  runner_pid: int = 0
  win_cs_title: str = field(init=False)

  def __post_init__(self) -> None:
    self.win_cs_title = f"[{self.login}] # CS"

  @staticmethod
  def generate_window_title(login: str) -> str:
    return f"[{login}] # CS"

  def stop_account(self, settings) -> bool:
    from core.services.process import ProcessService

    if self.runner_pid > 0:
      ProcessService.kill_by_pid(self.runner_pid)
      return True

    if settings.use_sandbox:
      import os
      from core.services.sandbox import SandboxieService

      box_name = SandboxieService.sanitize_box_name(self.login)
      ProcessService.kill_sandbox_box(
        sandboxie_path=os.path.join(SANDBOX_PATH, "Start.exe"),
        box_name=box_name,
      )

    return False
