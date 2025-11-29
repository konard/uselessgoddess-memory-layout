import asyncio
from typing import Tuple
from core.panel.state import State
from core.context import Context
from core.logging import get_logger
from core.services.cs_controller import CS2Controller
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
from resources import game_constants
from states.types import PartySchema
from states.wait_for_game import WaitForGame

logger = get_logger("state.select_map")


class SelectMap(State):
  def __init__(self, party_schema: Tuple[PartySchema, PartySchema]):
    self.party_schema = party_schema

  async def execute(self, ctx: Context):
    logger.info("Selecting map")

    for party in self.party_schema:
      WindowService.focus_window(party.leader.win_cs_title)

      CS2Controller.click(**game_constants.play_button, account=party.leader)
      CS2Controller.click(**game_constants.real_games, account=party.leader)

      if party.farm_mode == FarmMode.TWO_BY_TWO:
        CS2Controller.click(**game_constants.real_games, account=party.leader)

        CS2Controller.click(
          **game_constants.wingman_button, account=party.leader
        )

        await CS2Controller.click_bulk_async(
          "resources/img/check.png", party.leader, 0.9
        )

        await asyncio.sleep(0.3)

        CS2Controller.click_if_exists(
          "resources/img/inferno_badge.png", party.leader, 0.9
        )

    return WaitForGame(self.party_schema)
