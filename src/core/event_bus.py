from __future__ import annotations

from typing import Any, Callable, DefaultDict, List
from collections import defaultdict

from core.logging import get_logger

Callback = Callable[..., None]


class EventBus:
  """Простая шина событий на коллбэках.

  API:
  - subscribe(event_name, callback)
  - emit(event_name, **kwargs)
  """

  def __init__(self) -> None:
    self._logger = get_logger("EventBus")
    self._subscribers: DefaultDict[str, List[Callback]] = defaultdict(list)

  def subscribe(self, event_name: str, callback: Callback) -> None:
    self._subscribers[event_name].append(callback)

  def emit(self, event_name: str, **kwargs: Any) -> None:
    for callback in list(self._subscribers.get(event_name, [])):
      try:
        callback(**kwargs)
      except Exception as exc:  # noqa: BLE001
        self._logger.exception(
          "Ошибка обработчика события '%s': %s", event_name, exc
        )
