from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Optional

from core.logging import get_logger

if TYPE_CHECKING:
  from core.account import Account

logger = get_logger("event_service")


class EventService:
  def __init__(self):
    # data, event, expiration_time
    self._events: dict[str, dict[str, tuple[Any, asyncio.Event, float | None]]] = {}

  async def wait_for_event(
    self, account: Account, event_name: str, timeout: float | None = None
  ) -> Any:
    login = account.login

    if login not in self._events:
      self._events[login] = {}

    if event_name not in self._events[login]:
      self._events[login][event_name] = (None, asyncio.Event(), None)

    _, event, _ = self._events[login][event_name]

    try:
      await asyncio.wait_for(event.wait(), timeout=timeout)
    except TimeoutError as error:
      logger.debug(f"Timeout waiting for event {event_name} for {login}")
      raise Exception(f"Timeout waiting for event {event_name} for {login}") from error

    if login not in self._events or event_name not in self._events[login]:
      return None

    data, _, expiration = self._events[login][event_name]

    # Check if event is expired
    if expiration is not None and time.time() > expiration:
      logger.debug(f"Event {event_name} for {login} expired")
      event.clear()
      self._events[login][event_name] = (None, event, None)
      return None

    event.clear()
    self._events[login][event_name] = (
      None,
      event,
      None,
    )  # Reset data and expiration

    return data

  def emit_event(
    self, login: str, event_name: str, data: Any, ttl: float | None = None
  ) -> bool:
    if login not in self._events:
      self._events[login] = {}

    expiration = time.time() + ttl if ttl is not None else None

    if event_name in self._events[login]:
      _, event, _ = self._events[login][event_name]
      self._events[login][event_name] = (data, event, expiration)
      event.set()
    else:
      event = asyncio.Event()
      self._events[login][event_name] = (data, event, expiration)
      event.set()

    logger.trace(f"Event {event_name} emitted for {login} (TTL: {ttl})")
    return True

  def clear_event(self, login: str, event_name: str):
    if login in self._events and event_name in self._events[login]:
      del self._events[login][event_name]
