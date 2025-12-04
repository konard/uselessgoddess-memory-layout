import asyncio
from sre_parse import State
from typing import Tuple
from core import game_constants
from core.context import Context
from core.services.cs_controller import CS2Controller
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
import states
from states.types import PartySchema


class ShuffleLobby(State):
  def __init__(self, party_schema: Tuple[PartySchema, PartySchema]):
    self.party_schema: Tuple[PartySchema, PartySchema] = party_schema

  async def execute(self, ctx: Context):
    new_party_schema = []

    if self.party_schema[0].farm_mode == FarmMode.TWO_BY_TWO:
      side_a = PartySchema(
        leader=self.party_schema[0].leader,
        members=[self.party_schema[1].leader],
      )
      side_b = PartySchema(
        leader=self.party_schema[1].members[0],
        members=[self.party_schema[0].members[0]],
      )
      new_party_schema = [side_a, side_b]

    if len(new_party_schema) == 0:
      raise Exception("No members in party")

    for party in new_party_schema:
      for account in party.all:
        await WindowService.focus_window_async(account.win_cs_title)
        await asyncio.sleep(0.3)
        await CS2Controller.click_async(
          **game_constants.open_side_bar, account=account
        )
        await asyncio.sleep(0.3)
        await CS2Controller.click_if_exists_async("img/exit.png", account, 0.9)
        await asyncio.sleep(0.3)

    return states.MakeLobbies(new_party_schema)
