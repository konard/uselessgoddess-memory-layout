import asyncio
import contextlib
import threading
from collections.abc import Callable

import uvicorn
from fastapi import FastAPI, Request

from core.logging import get_logger

from .analyzer import GSIAnalyzer
from .events import GSIEvent
from .models import GameState

logger = get_logger("sv.gsi")


class GSIService:
  def __init__(self, port: int = 3000):
    self.port = port
    self.app = FastAPI()
    self._setup_routes()

    self.analyzer = GSIAnalyzer()
    self.current_state: GameState | None = None

    self._subscribers: dict[type[GSIEvent], list[Callable]] = {}
    self._global_subscribers: list[Callable[[GameState], None]] = []

    self._server_thread: threading.Thread | None = None
    self._server: uvicorn.Server | None = None
    self._running = False

  def _setup_routes(self):
    @self.app.post("/")
    @self.app.post("/gsi")
    async def receive_gsi(request: Request):
      if not self._running:
        return {"status": "ignored"}

      try:
        data = await request.json()
        self._process_data(data)
        return {"status": "ok"}
      except Exception as e:
        logger.error(f"Error parsing GSI: {e}")
        return {"status": "error"}

  def _process_data(self, data: dict):
    try:
      new_state = GameState.from_dict(data)
      self.current_state = new_state

      for cb in self._global_subscribers:
        with contextlib.suppress(Exception):
          cb(new_state)

      events = self.analyzer.analyze(new_state)

      for event in events:
        event_type = type(event)
        if event_type in self._subscribers:
          for cb in self._subscribers[event_type]:
            try:
              if asyncio.iscoroutinefunction(cb):
                loop = asyncio.new_event_loop()
                loop.run_until_complete(cb(event))
                loop.close()
              else:
                cb(event)
            except Exception as e:
              logger.error(f"Error in GSI handler {cb}: {e}")

    except Exception as e:
      logger.error(f"Failed to process GSI payload: {e}")

  def start(self):
    if self._running:
      return

    self._running = True

    config = uvicorn.Config(
      app=self.app,
      host="127.0.0.1",
      port=self.port,
      log_level="critical",
      access_log=False,
      loop="asyncio",
    )
    self._server = uvicorn.Server(config)

    def run_server():
      self._server.run()

    self._server_thread = threading.Thread(target=run_server, daemon=True)
    self._server_thread.start()

    logger.debug(f"server started on port {self.port}")

  def stop(self):
    if not self._running or not self._server:
      return

    self._running = False
    self._server.should_exit = True
    if self._server_thread:
      self._server_thread.join(timeout=2)
    logger.info("GSI Server stopped")

  def subscribe(self, event_type: type[GSIEvent], callback: Callable):
    if event_type not in self._subscribers:
      self._subscribers[event_type] = []
    self._subscribers[event_type].append(callback)

  def unsubscribe(self, event_type: type[GSIEvent], callback: Callable):
    if event_type in self._subscribers and callback in self._subscribers[event_type]:
      self._subscribers[event_type].remove(callback)

  def listen_raw(self, callback: Callable[[GameState], None]):
    self._global_subscribers.append(callback)

  def unlisten_raw(self, callback: Callable[[GameState], None]):
    if callback in self._global_subscribers:
      self._global_subscribers.remove(callback)
