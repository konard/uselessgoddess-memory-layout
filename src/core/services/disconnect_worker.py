import asyncio
from typing import TYPE_CHECKING
from core.panel.state import StateManager
from core.services.cs_controller import CS2Controller
from states.disconnect import DisconnectState, DisconnectType
from states.match.state import MatchState

if TYPE_CHECKING:
  from core.context import Context


class DisconnectWorker:
  def __init__(self, stateManager: StateManager, ctx: "Context"):
    self.stateManager = stateManager
    self.ctx = ctx

  async def run(self):
    while True:
      disconnected_accounts = []
      for account in self.ctx.launched_accounts:
        is_disconnected = CS2Controller.check_if_exists(
          "img/disconnected.png", account
        )
        if is_disconnected:
          disconnected_accounts.append(account)

      if len(disconnected_accounts) > 0:
        current_state = self.stateManager.acquire_state()
        if isinstance(current_state, MatchState):
          await self.stateManager.into_state(
            DisconnectState(DisconnectType.MATCH, disconnected_accounts)
          )
          await asyncio.sleep(120)
        else:
          await self.stateManager.into_state(
            DisconnectState(DisconnectType.LOBBY, disconnected_accounts)
          )
          await asyncio.sleep(120)
      await asyncio.sleep(3)
