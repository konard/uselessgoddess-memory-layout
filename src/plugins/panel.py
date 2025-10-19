from abc import ABC, abstractmethod
from threading import Thread
from typing import Dict, Type, Callable

from core.logging import get_logger

logger = get_logger("yacs.state")


class Context:
  pass


class Message:
  # gui layout of messages
  @abstractmethod
  def layout(self):
    pass


Handlers: Type = Dict[Type[Message], Callable]


_message_handlers: Handlers = {}


def handles(message_type: Type[Message]):
  def decorator(handler: Callable):
    if not issubclass(message_type, Message):
      raise TypeError("Decorator @handles is available  for `Message` types")
    _message_handlers[message_type] = handler
    return handler

  return decorator


class State:
  pass


class State(ABC):
  _handler_map: Handlers = {}

  # @abstractmethod -- for `Idle`
  def react(self, message: Message):
    handler = self._handler_map.get(type(message))

    if handler:
      handler(self, message)
    else:
      logger.warn(f"unexpected message type: {type(message)}")
    pass

  @abstractmethod
  def execute(self, _: Context) -> State:
    pass


class Idle(State):
  def __init__(self):
    logger.info("enter idle")

  def react(self, message: Message):
    pass

  def execute(self, _: Context) -> State:
    import time

    while True:
      time.sleep(1)
      logger.info("idle")
      pass


class Panel:
  state = None
  ctx = Context()

  def __init__(self):
    self._enter_state(Idle())

  def _execute_wrapper(self, state: State):
    def inner():
      self._enter_state(state.execute(self.ctx))

    return inner

  def _enter_state(self, state: State):
    self.state = Thread(target=self._execute_wrapper(state), daemon=True)
    self.state.start()

