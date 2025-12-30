from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from core.logging import get_logger
from core.services.license import LicenseKind
from core.utils import name_of, type_of

from .message import Message

if TYPE_CHECKING:
  from core.context import Context
  from states import LicenseState

from constants import CHECK_LICENSE

logger = get_logger("state")


def handles(message_type: type[Message]):
  def decorator(func):
    func._handled_message_type = message_type
    return func

  return decorator


class State:
  async def execute(self):
    pass

  async def react(self, manager: StateManager, message: Message):
    if not hasattr(self, "_message_handlers"):
      self._message_handlers = {}
      for attr_name in dir(self):
        attr = getattr(self, attr_name)
        if callable(attr) and hasattr(attr, "_handled_message_type"):
          msg_type = attr._handled_message_type
          self._message_handlers[msg_type] = attr

    handler = self._message_handlers.get(type(message))
    if handler:
      await handler(message, manager)
    else:
      logger.warn(f"`{type_of(message)}` handler is not registred for `{name_of(self)}`")

  def layout(self, ctx: Context, dispatch: Callable[[Message], None]):
    return []

  # helpers

  def block(self, func):
    async def inner(*args, **kwargs):
      loop = asyncio.get_running_loop()
      # TODO: !should we use custom pool
      await loop.run_in_executor(None, func, *args, **kwargs)

    return inner

  def then(self, next: State) -> State:
    _base = self.execute

    async def _execute(ctx: Context):
      result = await _base(ctx)

      if result is not None:
        return result

      return next

    self.execute = _execute
    return self


class StateManager:
  def __init__(self, context: Context, callback: Callable):
    self.context = context
    self._current_state: State | None = None
    self._current_task: asyncio.Task | None = None
    self._update_ui = callback
    self._state_start_time = time.time()

  def acquire_state(self) -> State | None:
    return self._current_state

  def is_state_equal(self, state: State) -> bool:
    return self._current_state is state

  def update_ui(self):
    self._update_ui()

  async def into_state(self, state: State, check: bool = True):
    logger.trace(
      f"is license valid {self.context.lic.is_working()}: {self.context.lic.state()}"
    )

    if CHECK_LICENSE and check and not self.context.lic.is_working():
      title = "Work Paused"
      desc = "Unknown reason"

      kind = self.context.lic.state()

      if kind == LicenseKind.PAUSED_NETWORK:
        title = "Connection Lost"
        desc = "Internet connection is unstable. Waiting for recovery..."
      elif kind == LicenseKind.PAUSED_LIMIT:
        title = "Session Limit Reached"
        desc = "Too many active sessions. Close other instances or wait."
      elif kind == LicenseKind.INVALID:
        title = "License expired"
        desc = "Please renew your license"

      logger.warning(f"License suspended ({kind.value}). Please enter new license.")
      import states

      await self.into_state(states.LicenseState(state, title, desc), check=False)
      return

    if self._current_state:
      duration = time.time() - self._state_start_time
      payload = {
        "state": name_of(self._current_state),
        "duration": duration,
      }
      asyncio.create_task(self.context.metrics.send("state", payload))

    self._state_start_time = time.time()

    if self._current_task and not self._current_task.done():
      self._current_task.cancel()
      with contextlib.suppress(asyncio.CancelledError):
        await self._current_task

    self._current_state = state

    self._update_ui()
    self._current_task = asyncio.create_task(
      self._current_state.execute(self.context),
    )
    self._current_task.add_done_callback(self._handle_execute_completion)

  async def dispatch(self, message: Message):
    if self._current_state:
      await self._current_state.react(self, message)

  def _handle_execute_completion(self, task: asyncio.Task):
    if task is not self._current_task:
      return

    name = name_of(self._current_state)
    try:
      next_state = task.result()
    except asyncio.CancelledError:
      return
    except Exception as e:
      logger.error(f"error in state {name}: {e}")

      import traceback

      logger.error(traceback.format_exc())
      return

    if next_state:
      asyncio.create_task(self.into_state(next_state))
    else:
      logger.error(f"there was no `return` from `{name}.execute`")
