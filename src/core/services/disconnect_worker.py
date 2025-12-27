import asyncio
from typing import TYPE_CHECKING
from core import game_constants
from core.panel.state import StateManager
from core.services.cs_controller import CS2Controller
from core.services.windows_service import WindowService
from states.continue_farm import ContinueFarm
from states.disconnect import DisconnectState, DisconnectType
from states.make_lobbies.make_lobbies import MakeLobbies
from states.match.state import MatchState
from core.logging import get_logger
from states.select_accounts import SelectAccounts

if TYPE_CHECKING:
  from core.context import Context

logger = get_logger("sv.disconnect")


class DisconnectWorker:
  def __init__(self, stateManager: StateManager, ctx: "Context"):
    self.stateManager = stateManager
    self.ctx = ctx

  async def run(self):
    while True:
      disconnected_accounts = []
      is_match = False

      farm_mode = self.ctx.s.system.farm_mode

      launched_accounts = len(self.ctx.launched_accounts)
      current_state = self.stateManager.acquire_state()

      # Fix: use isinstance because current_state is an instance, and the list contains classes
      should_fill_accounts = isinstance(
        current_state, (MakeLobbies, ContinueFarm)
      )

      if (
        launched_accounts != game_constants.farm_mode_size[farm_mode]
        and should_fill_accounts
      ):
        await self.stateManager.into_state(
          SelectAccounts(game_constants.farm_mode_size[farm_mode])
        )
        continue

      for account in self.ctx.launched_accounts:
        is_disconnected = await CS2Controller.check_if_exists_async(
          "img/disconnected.png", account
        )

        if is_disconnected:
          await WindowService.focus_window_async(account.win_cs_title)
          await asyncio.sleep(0.1)
          if not await CS2Controller.check_if_exists_async(
            "img/play.png", account
          ):
            is_match = True

        if is_disconnected:
          disconnected_accounts.append(account)

      if len(disconnected_accounts) > 0:
        logger.trace(f"Disconnected accounts: {disconnected_accounts}")
        if is_match:
          await self.stateManager.into_state(
            DisconnectState(DisconnectType.MATCH, disconnected_accounts)
          )
          await asyncio.sleep(20)
        else:
          await self.stateManager.into_state(
            DisconnectState(DisconnectType.LOBBY, disconnected_accounts)
          )
          await asyncio.sleep(20)
      await asyncio.sleep(3)
