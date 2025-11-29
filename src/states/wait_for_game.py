import asyncio
from core.services.windows_service import WindowService
import states
from typing import Optional, Tuple
from core.panel.state import State
from core.services.cs_controller import CS2Controller
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
    logger.info("Waiting for game")

    logger.info(f"Waiting for match_id for {len(self.party_schema)} accounts")

    while True:
      leaders = [party.leader for party in self.party_schema]

      await Yass.press_resource_async(
        "resources/img/ready_button_left_corner.png", leaders
      )

      if not await ctx.gc.player_info_service.matcher_service.wait_for_match_id(
        leaders
      ):
        logger.error("Failed to get match_id for all accounts")

        await Yass.press_resource_async(
          "resources/img/cancel_button_left_corner.png", leaders
        )

        await asyncio.sleep(1)
        continue

      for party in self.party_schema:
        for account in party.all:
          await CS2Controller.click_async(
            **game_constants.accept_game_button, account=account
          )
          return states.Idle()
