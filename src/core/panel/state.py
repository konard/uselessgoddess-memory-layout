from __future__ import annotations

import asyncio

from typing import Optional, Callable, Type, TYPE_CHECKING

if TYPE_CHECKING:
  from core.context import Context

from core.logging import get_logger
from core.utils import name_of, type_of
from .message import Message

logger = get_logger("state")


def handles(message_type: Type[Message]):
  def decorator(func):
    func._handled_message_type = message_type
    return func

  return decorator


class State:
  async def execute(self, ctx: Context):
    pass

  async def react(self, manager: "StateManager", message: Message):
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
      logger.warn(
        f"`{type_of(message)}` handler is not registred for `{name_of(self)}`"
      )

  def layout(self, ctx: Context, dispatch: Callable[[Message], None]):
    return []

  # helpers

  def block(self, func):
    async def inner(*args, **kwargs):
      loop = asyncio.get_running_loop()
      # TODO: !should we use custom pool
      await loop.run_in_executor(None, func, *args, **kwargs)

    return inner

  def then(self, next: "State") -> "State":
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
    self._current_state: Optional[State] = None
    self._current_task: Optional[asyncio.Task] = None
    self._update_ui = callback

  def acquire_state(self) -> Optional[State]:
    return self._current_state

  def update_ui(self):
    self._update_ui()

  async def into_state(self, state: State):
    if self._current_task and not self._current_task.done():
      self._current_task.cancel()
      try:
        await self._current_task
      except asyncio.CancelledError:
        pass

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
