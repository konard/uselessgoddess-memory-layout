import asyncio
from core.services.windows_service import WindowService
import states
from typing import Optional, Tuple
from core.panel.state import State
from core.services import CS2Controller
from core.yass import Yass
from core import game_constants
from states.types import PartySchema
from core.context import Context
from core.logging import get_logger
from utils.name_generator import generate_preset_name

logger = get_logger("state.wait_for_game")


class WaitForGame(State):
  def __init__(
    self,
    party_schema: Tuple[PartySchema, PartySchema],
    retries: Optional[int] = None,
  ):
    self.party_schema = party_schema
    self.retries = retries or 0

  async def execute(self, ctx: Context):
    from states.match.state import MatchState

    logger.info(f"Waiting for match_id for {len(self.party_schema)} accounts")

    count = 0

    leaders = [party.leader for party in self.party_schema]

    print(leaders, "leaders")

    while True:
      if count >= ctx.su.times_to_shuffle:
        return states.ShuffleLobby(self.party_schema, retries=self.retries + 1)

      await Yass.press_resource_async(
        "img/ready_button_left_corner.png", leaders
      )

      while not ctx.gc.lobby_service.match_warning.is_searching(leaders[0]):
        await Yass.press_resource_single_async(
          "img/cancel_button_left_corner.png", leaders[1]
        )

        await asyncio.sleep(0.5)

        await Yass.press_resource_single_async(
          "img/ready_button_left_corner.png", leaders[0]
        )
        print("Press 1")
        await asyncio.sleep(1)

      while not ctx.gc.lobby_service.match_warning.is_searching(leaders[1]):
        await Yass.press_resource_single_async(
          "img/cancel_button_left_corner.png", leaders[0]
        )

        await asyncio.sleep(0.5)

        await Yass.press_resource_single_async(
          "img/ready_button_left_corner.png", leaders[1]
        )

        print("Press 2")
        await asyncio.sleep(1)

      await asyncio.sleep(3)
      print("Verif")

      await Yass.press_resource_async(
        "img/ready_button_left_corner.png", leaders
      )

      await asyncio.sleep(1)

      if not await ctx.gc.player_info_service.matcher_service.wait_for_match_id(
        leaders
      ):
        logger.warn("Failed to get same match_ids for all accounts")

        await Yass.press_resource_async(
          "img/cancel_button_left_corner.png", leaders
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

    ctx.blacklisted_accounts.clear()

    found_preset = ctx.presets.find_preset_by_game_schema(self.party_schema)

    if found_preset:
      if found_preset.has_error:
        found_preset.has_error = False
        ctx.presets.save()
        logger.info(f"Cleared error flag for preset {found_preset.name}")
    else:
      current_logins = []
      for party in self.party_schema:
        current_logins.extend([acc.login for acc in party.all])

      new_preset_name = generate_preset_name()

      logger.info(
        f"Current match accounts not in any preset. Creating {new_preset_name}"
      )

      if ctx.presets.create_preset(new_preset_name):
        ctx.presets.update_preset_accounts(new_preset_name, current_logins)

      await ctx.metrics.send("srt", {"routes": ctx.srt.get_allowed_routes()})

    return MatchState(self.party_schema)
