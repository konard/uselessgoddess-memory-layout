import asyncio
import states

from enum import Enum
from core.panel.state import State
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.services.cs_controller import CS2Controller
from core.services.windows_service import WindowService

logger = get_logger("state.disconnect")


class DisconnectType(str, Enum):
  MATCH = "match"
  LOBBY = "lobby"


class DisconnectState(State):
  def __init__(
    self, disconnect_type: DisconnectType, disconnected_accounts: list[Account]
  ):
    self.disconnect_type = disconnect_type
    self.disconnected_accounts = disconnected_accounts

  async def execute(self, ctx: Context):
    for account in self.disconnected_accounts:
      await asyncio.sleep(1)
      await WindowService.focus_window_async(account.win_cs_title)
      await asyncio.sleep(0.5)
      await CS2Controller.wait_for_image_async("img/disconnected.png", account)
      await asyncio.sleep(0.5)
      await CS2Controller.click_if_exists_async("img/ok.png", account, 0.9)
      await asyncio.sleep(0.5)

    match self.disconnect_type:
      case DisconnectType.MATCH:
        for account in self.disconnected_accounts:
          await WindowService.focus_window_async(account.win_cs_title)
          await asyncio.sleep(0.5)
          await CS2Controller.click_if_exists_async(
            "img/recon_to_match.png", account, 0.9
          )
          await asyncio.sleep(1)

          return states.MatchState(None)
      case DisconnectType.LOBBY:
        return states.ContinueFarm(None)
