import asyncio
from typing import Optional

import states
from core.context import Context
from core.logging import get_logger
from core.panel import State
from core.services.windows_service import WindowService
from states.types import GameSchema
from ui.widgets import Button, Label, LabelType, VStack

from .worker import MatchWorker

logger = get_logger("state.match")


class MatchState(State):
  def __init__(self, game_schema: GameSchema | None):
    self.worker: MatchWorker | None = None
    self.lbl_status = Label("Initializing...")
    self.game_schema = game_schema
    self.running = True

  def layout(self, ctx: Context, dispatch):
    return [
      VStack(
        Label("Auto Match", LabelType.HEADER),
        self.lbl_status,
        Button("Stop", on_click=lambda _: self.stop()),
      )
    ]

  def stop(self):
    if self.worker:
      self.worker.running = False
    self.running = False

  async def cleanup(self):
    await super().cleanup()

    if self.worker:
      self.worker.running = False

      await asyncio.to_thread(self.worker.join, timeout=2.0)

  async def execute(self, ctx: Context):
    from states.continue_farm import ContinueFarm

    launched_accounts = WindowService.scan_cs2_windows(ctx.accounts(), values=True)

    self.worker = MatchWorker(ctx, launched_accounts)

    ctx.gsi.listen_raw(self.worker.on_game_state)
    self.worker.start()

    try:
      while self.running and self.worker and self.worker.is_alive():
        self.lbl_status.set(f"{self.worker.status}")
        await asyncio.sleep(1.0)
        self.worker.lifetime += 1.0
    finally:
      if self.worker:
        self.worker.running = False
        ctx.gsi.unlisten_raw(self.worker.on_game_state)
        self.worker.stop()

      try:
        score = list(self.worker.score.values())
        await ctx.send_message(f"Match finished with {score[0]}:{score[1]}")
      except:  # noqa: E722
        pass

    if self.running:
      return ContinueFarm(self.game_schema)
    else:
      return states.Idle()
