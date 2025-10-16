from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


from .config_manager import ConfigManager
from .event_bus import EventBus
from .gui_executor import GuiExecutor
from .logger import get_logger
from .accounts.model import Account
from .root_fs import root_fs

logger = get_logger("AppState")

@dataclass
class AppState:
    """Глобальный стейт приложения.

    Предназначен для централизованного хранения общих объектов и данных,
    чтобы их можно было легко передавать в плагины и окна.
    """

    config: ConfigManager
    event_bus: EventBus
    gui_exec: GuiExecutor | None = None
    window: Any | None = None
    plugin_manager: Any | None = None
    accounts: List[Account] = field(default_factory=list)
    selected_account: Optional[Account] = None

    def as_context(self) -> Dict[str, Any]:
        """Собирает контекст, совместимый с текущим API плагинов."""
        return {
            "config": self.config,
            "event_bus": self.event_bus,
            "gui_exec": self.gui_exec,
            "window": self.window,
            "state": self,  # новое поле для удобства
        }


_APP_STATE: AppState | None = None

def load_accounts(file: str) -> List[Account]:
    """Загружает список аккаунтов из JSON-файла относительно корня проекта."""
    accounts: List[Account] = []
    if not root_fs.exists(file):
        return accounts

    data = root_fs.read_json(file)
    list_data = list(data.values())
    for account in list_data:
        accounts.append(Account.from_json(account))
    return accounts

def init_app_state(config: ConfigManager, event_bus: EventBus) -> AppState:
    global _APP_STATE

    accounts = load_accounts(config.get("accounts_file", "data/accounts.json"))
    logger.trace(f"Загружено {len(accounts)} аккаунтов")


    _APP_STATE = AppState(config=config, event_bus=event_bus, accounts=accounts)
    logger.trace("AppState инициализирован")
    return _APP_STATE


def get_app_state() -> AppState:
    assert _APP_STATE is not None, "AppState не инициализирован. Вызовите init_app_state() сначала."
    return _APP_STATE


