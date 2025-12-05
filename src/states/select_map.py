import asyncio
from typing import Tuple
from core.panel.state import State
from core.context import Context
from core.logging import get_logger
from core.services.cs_controller import CS2Controller
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
from core import game_constants
from states.types import PartySchema

logger = get_logger("state.select_map")


class SelectMap(State):
  def __init__(self, party_schema: Tuple[PartySchema, PartySchema]):
    self.party_schema = party_schema

  async def execute(self, ctx: Context):
    from states.wait_for_game import WaitForGame

    logger.info("Selecting map")

    for party in self.party_schema:
      await WindowService.focus_window_async(party.leader.win_cs_title)

      await CS2Controller.click_async(
        **game_constants.play_button, account=party.leader
      )
      await CS2Controller.wait_for_image_async("img/play.png", party.leader)

      await CS2Controller.click_async(
        **game_constants.real_games, account=party.leader
      )

      if party.farm_mode == FarmMode.TWO_BY_TWO:
        await CS2Controller.click_async(
          **game_constants.real_games, account=party.leader
        )

        await CS2Controller.click_async(
          **game_constants.wingman_button, account=party.leader
        )

        await asyncio.sleep(3)

        await CS2Controller.click_bulk_async(
          "img/check_2.png", party.leader, 0.8
        )

        await asyncio.sleep(4)

        await CS2Controller.click_if_exists_async(
          "img/inferno_badge.png", party.leader, 0.8
        )

        await asyncio.sleep(1)

    return WaitForGame(self.party_schema)
