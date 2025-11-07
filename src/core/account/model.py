from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Account:
  login: str
  password: str
  shared_secret: str
  identity_secret: str | None
  steam_id: str

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
