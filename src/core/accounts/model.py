from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(slots=True)
class Account:
    """Основная модель данных аккаунта"""
    login: str
    password: str
    shared_secret: str
    steam_id: str
    
    runner_pid: int = 0
    posX: int = 0
    posY: int = 0

    win_cs_title: str = field(init=False)
    status: str = "OFF"

    def __post_init__(self) -> None:
        """Инициализация вычисляемых полей"""
        self.win_cs_title = f"[{self.login}] # CS"

    @staticmethod
    def from_json(data: dict) -> "Account":
        return Account(
            login=data["login"],
            password=data.get("password", ""),
            shared_secret=data.get("shared_secret", ""),
            steam_id=data.get("steam_id", ""),
        )
    def to_json(self) -> dict:
        return {
            "login": self.login,
            "password": self.password,
            "shared_secret": self.shared_secret,
            "steam_id": self.steam_id,
        }
