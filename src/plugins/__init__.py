"""Plugins package: manager and available plugins."""

from typing import Protocol, Dict, Any


class PluginBase(Protocol):
    """Интерфейс плагина.

    Каждый плагин должен реализовать методы:
    - setup(app_context): инициализация/регистрация
    - teardown(): корректное отключение
    - meta: свойство с метаданными (dict)
    """

    def setup(self, app_context: Dict[str, Any]) -> None: ...

    def teardown(self) -> None: ...

    @property
    def meta(self) -> Dict[str, Any]: ...


