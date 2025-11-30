import asyncio
from typing import Optional
from core import context, game_constants
from core.account.model import FarmStatus
from core.logging import get_logger
from core.panel import state
from core.services.cs_controller import CS2Controller
from core.services.windows_service import WindowService
from states.make_lobbies.generate_party_schema import generate_party_schema
from states.types import GameSchema

logger = get_logger("state.continue_farm")


class ContinueFarm(state.State):
  def __init__(self, game_schema: Optional[GameSchema]):
    self.game_schema = game_schema

  async def execute(self, ctx: context.Context):
    from states.make_lobbies.make_lobbies import MakeLobbies
    from states.select_map import SelectMap

    if self.game_schema is None:
      launched_accounts = WindowService.scan_cs2_windows(
        ctx.accounts(), values=True
      )
      self.game_schema = generate_party_schema(
        launched_accounts, ctx.settings.system.farm_mode
      )

    show_must_go_on = False

    accounts = [account for party in self.game_schema for account in party.all]

    for account in accounts:
      logger.info(f"account: {account.login} is {account.lock.status}")
      if account.lock.status == FarmStatus.NEED_TO_FARM:
        show_must_go_on = True
        break

    logger.info(f"show_must_go_on: {show_must_go_on}")
    if show_must_go_on:
      all_lobbies = True

      for party_schema in self.game_schema:
        account = party_schema.leader

        await WindowService.focus_window_async(account.win_cs_title)

        await asyncio.sleep(0.3)

        await CS2Controller.wait_for_image_async(
          "resources/img/play.png", account
        )

        await CS2Controller.click_if_exists_async(
          "resources/img/close_reward.png", account, 0.9, True
        )

        await asyncio.sleep(0.3)

        await CS2Controller.click_async(
          **game_constants.open_side_bar, account=account
        )

        await asyncio.sleep(0.3)

        if not await CS2Controller.check_if_exists_async(
          "resources/img/exit.png", account, 0.9
        ):
          all_lobbies = False

      if all_lobbies:
        return SelectMap(self.game_schema)
      else:
        for account in accounts:
          await CS2Controller.click_async(
            **game_constants.open_side_bar, account=account
          )

          await asyncio.sleep(0.3)

          await CS2Controller.click_if_exists_async(
            "resources/img/exit.png", account, 0.9, True
          )

          await asyncio.sleep(0.3)

          return MakeLobbies(self.game_schema)
