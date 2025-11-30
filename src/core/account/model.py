from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from enum import Enum

from core.logging import get_logger
from .lock import AccountsLock


logger = get_logger("account.model")


class FarmStatus(str, Enum):
  NEED_TO_FARM = "need_to_farm"
  CAN_BE_LOOTED = "can_be_looted"
  FARMED = "farmed"
  TRADED = "traded"


status_map = {
  FarmStatus.NEED_TO_FARM: FarmStatus.CAN_BE_LOOTED,
  FarmStatus.CAN_BE_LOOTED: FarmStatus.FARMED,
  FarmStatus.FARMED: FarmStatus.TRADED,
  FarmStatus.TRADED: FarmStatus.NEED_TO_FARM,
}


class Metadata(Dict[str, Any]):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.lvl = 0
    self.xp = 0
    self.invite = ""
    self.status = FarmStatus.NEED_TO_FARM
    self.vac_banned = False
    self.refresh_token = ""


@dataclass(slots=True)
class AccountMetadata:
  _data: Dict[str, Any] = field(default_factory=Metadata, init=False)
  _lock: AccountsLock | None = field(init=False, default=None)
  _login: str = field(init=False, default="")

  def update_from_lock(self, login: str, lock: AccountsLock) -> None:
    self._lock = lock
    self._login = login
    info = lock.get_account_info(login)
    if info:
      self._data.update(info)

  def save_to_lock(self) -> None:
    if self._lock and self._login:
      self._lock.set_account_info(self._login, **self._data)

  @property
  def lvl(self) -> int | None:
    return self._data.get("lvl")

  @lvl.setter
  def lvl(self, value: int) -> None:
    self._data["lvl"] = value
    if self._lock:
      self._lock.set_field(self._login, "lvl", value)

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
    self._data["xp"] = value
    if self._lock:
      self._lock.set_field(self._login, "xp", value)

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
    current_status = self._data.get("status")
    if status_map[current_status] != value:
      logger.trace(f"Invalid status transition: {current_status} -> {value}")
      return

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

  def stop_account(self) -> bool:
    if self.runner_pid > 0:
      # Ленивый импорт для избежания циклических зависимостей
      from core.services.process import ProcessService

      ProcessService.kill_by_pid(self.runner_pid)
      return True
    return False
