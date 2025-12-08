import asyncio
from core.panel.state import State
from core.context import Context
from core.logging import get_logger
from core.services.settings import FarmMode
from states.types import GameSchema
from states.launch_accounts import LaunchAccounts
from states.loot import LootAccounts

logger = get_logger("state.template")


class StartUnfarmed(State):
  def __init__(self, game_schema: GameSchema):
    self.game_schema = game_schema

  async def execute(self, ctx: Context):
    accounts = [account for party in self.game_schema for account in party.all]

    for account in accounts:
      account.stop_account()

    await asyncio.sleep(5)

    unfarmed_accounts = ctx.unfarmed_accounts()

    if self.game_schema[0].farm_mode == FarmMode.TWO_BY_TWO:
      if len(unfarmed_accounts) < 4:
        return LootAccounts(ctx.accounts())
      return LaunchAccounts(unfarmed_accounts[:4])

    elif self.game_schema[0].farm_mode == FarmMode.FIVE_BY_FIVE:
      if len(unfarmed_accounts) < 10:
        return LootAccounts(ctx.accounts())
      return LaunchAccounts(unfarmed_accounts[10:])
    else:
      raise ValueError(f"Invalid farm mode: {self.game_schema[0].farm_mode}")
