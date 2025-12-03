import asyncio
from core.services.windows_service import WindowService
import states
from typing import Tuple
from core.panel.state import State
from core.services import CS2Controller
from core.yass import Yass
from core import game_constants
from states.types import PartySchema
from core.context import Context
from core.logging import get_logger

logger = get_logger("state.wait_for_game")


class WaitForGame(State):
  def __init__(self, party_schema: Tuple[PartySchema, PartySchema]):
    self.party_schema = party_schema

  async def execute(self, ctx: Context):
    from states.match.state import MatchState

    logger.info(f"Waiting for match_id for {len(self.party_schema)} accounts")

    count = 0

    leaders = [party.leader for party in self.party_schema]

    print(leaders, "leaders")

    while True:
      if count >= ctx.su.times_to_shuffle:
        return states.ShuffleLobby(self.party_schema)

      await Yass.press_resource_async(
        "resources/img/ready_button_left_corner.png", leaders
      )

      print(1)
      while not ctx.gc.lobby_service.match_warning.is_searching(leaders[0]):
        await Yass.press_resource_single_async(
          "resources/img/cancel_button_left_corner.png", leaders[1]
        )
        await asyncio.sleep(0.5)
      print(2)

      while not ctx.gc.lobby_service.match_warning.is_searching(leaders[1]):
        await Yass.press_resource_single_async(
          "resources/img/cancel_button_left_corner.png", leaders[0]
        )
        await asyncio.sleep(0.5)

      await asyncio.sleep(1)
      print(3)

      await Yass.press_resource_async(
        "resources/img/ready_button_left_corner.png", leaders
      )

      if not await ctx.gc.player_info_service.matcher_service.wait_for_match_id(
        leaders
      ):
        logger.warn("Failed to get same match_ids for all accounts")

        await Yass.press_resource_async(
          "resources/img/cancel_button_left_corner.png", leaders
        )

        await asyncio.sleep(1)
        if ctx.ss.shuffle_lobbies:
          count += 1
        continue

      await asyncio.sleep(4)

      for party in self.party_schema:
        for account in party.all:
          await WindowService.focus_window_async(account.win_cs_title)

          await asyncio.sleep(0.5)

          await CS2Controller.click_async(
            **game_constants.accept_game_button, account=account
          )

          await asyncio.sleep(0.5)
      break

    await ctx.send_message("Match found")

    return MatchState(self.party_schema)
