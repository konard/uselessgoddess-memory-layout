import asyncio
import random

from core.account.model import FarmStatus
from core.context import Context
from core.logging import get_logger
from core.panel.state import State
from core.process_config import ConfigService
from core.services.settings import FarmMode
from states.farm import StartFarm
from states.loot import LootAccounts, claim_drop
from states.trade import process_trade
from states.types import GameSchema

logger = get_logger("state.start_unfarmed")


class StartUnfarmed(State):
  def __init__(self, game_schema: GameSchema):
    self.game_schema = game_schema

  async def execute(self, ctx: Context):
    accounts = [account for party in self.game_schema for account in party.all]

    config_service = ConfigService(ctx)
    for account in accounts:
      account.stop_account(ctx.su)

      config_service.delete_video_config(account.steam_id)

    await asyncio.sleep(5)

    for account in accounts:
      if ctx.settings.system.collect_drop:
        await claim_drop(self, account)
        await asyncio.sleep(1 + random.randint(0, 4))
        await process_trade(self, account, ctx.settings.user.trade_url)

    next_preset_accounts = self._find_next_preset(ctx)

    if next_preset_accounts:
      logger.info(f"Switching to next preset with {len(next_preset_accounts)} accounts")
      return StartFarm(next_preset_accounts)
    unfarmed_accounts = ctx.unfarmed_accounts()

    if self.game_schema[0].farm_mode == FarmMode.TWO_BY_TWO:
      if len(unfarmed_accounts) < 4:
        return LootAccounts(ctx.accounts())
      return StartFarm(unfarmed_accounts[:4])

    elif self.game_schema[0].farm_mode == FarmMode.FIVE_BY_FIVE:
      if len(unfarmed_accounts) < 10:
        return LootAccounts(ctx.accounts())
      return StartFarm(unfarmed_accounts[10:])
    else:
      raise ValueError(f"Invalid farm mode: {self.game_schema[0].farm_mode}")

  def _find_next_preset(self, ctx: Context):
    """Ищет следующий пресет, который нужно фармить (есть статус NEED_TO_FARM)."""
    presets = ctx.presets.get_all_presets()

    for preset in presets:
      if not preset.is_valid:
        continue

      status = preset.get_status(ctx)
      if status == FarmStatus.NEED_TO_FARM:
        accounts_to_launch = []
        for login in preset.accounts:
          acc = ctx.account.accounts.get(login)
          if acc:
            accounts_to_launch.append(acc)

        if len(accounts_to_launch) == len(preset.accounts):
          logger.info(f"Found next preset to farm: {preset.name}")
          return accounts_to_launch

    return None
