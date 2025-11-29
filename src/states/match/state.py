from typing import Optional

import asyncio
from core.panel import State
from core.context import Context
from core.logging import get_logger
from ui.widgets import Label, LabelType, Button, VStack

from .worker import MatchWorker

logger = get_logger("state.match")


class MatchState(State):
  def __init__(self, accounts: list):
    self.accounts = accounts
    self.worker: Optional[MatchWorker] = None
    self.lbl_status = Label("Initializing...")

  def layout(self, ctx: Context, dispatch):
    return [
      VStack(
        Label("Auto Match (Raw GSI)", LabelType.HEADER),
        self.lbl_status,
        Button("Stop", on_click=lambda _: self.stop()),
      )
    ]

  def stop(self):
    if self.worker:
      self.worker.stop()
    self.worker = None

  async def execute(self, ctx: Context):
    self.worker = MatchWorker(ctx, self.accounts)

    ctx.gsi.listen_raw(self.worker.on_game_state)
    self.worker.start()

    try:
      while self.worker and self.worker.is_alive():
        self.lbl_status.set(f"Status: {self.worker.status}")
        await asyncio.sleep(0.1)
    finally:
      if self.worker:
        ctx.gsi.unlisten_raw(self.worker.on_game_state)
        self.worker.stop()
      pass
