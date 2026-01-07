import asyncio
import datetime

import states
from core import context, game_constants
from core.account.model import FarmStatus, RunningAccount
from core.logging import get_logger
from core.panel import state
from core.services.cs_controller import CS2Controller
from core.services.windows_service import WindowService
from states.make_lobbies.generate_party_schema import generate_party_schema
from states.start_unfarmed import StartUnfarmed
from states.types import GameSchema
from utils.mem_reduct import clean_memory

logger = get_logger("state.continue_farm")


class ContinueFarm(state.State):
  def __init__(self, game_schema: GameSchema | None, delay: int = 20):
    self.game_schema = game_schema
    self.delay = delay

  async def check_if_all_in_lobby(self, accounts: list[RunningAccount]):
    clean_memory()

    all_in_lobby = True
    logger.info("Starting lobby check for accounts...")

    for account in accounts:
      logger.info(f"Checking lobby status for {account.login}")
      await WindowService.focus_window_async(account.win_cs_title)

      await asyncio.sleep(0.1)

      await CS2Controller.move_mouse_async(
        **game_constants.open_side_bar, account=account
      )

      await CS2Controller.wait_for_image_async("img/friend_id_modal.png", account)

      await asyncio.sleep(0.2)

      in_lobby = await CS2Controller.check_if_exists_async("img/exit.png", account, 0.9)
      logger.info(f"Account {account.login} 'exit.png' found: {in_lobby}")

      if not in_lobby:
        logger.warning(f"Account {account.login} seems NOT to be in lobby.")
        all_in_lobby = False
        break

    logger.info(f"check_if_all_in_lobby result: {all_in_lobby}")

    if not all_in_lobby:
      logger.info("Attempting to exit lobbies for all accounts due to failure...")
      for account in accounts:
        await WindowService.focus_window_async(account.win_cs_title)
        await CS2Controller.move_mouse_async(
          **game_constants.open_side_bar, account=account
        )

        await CS2Controller.wait_for_image_async("img/friend_id_modal.png", account)

        await CS2Controller.click_if_exists_async("img/exit.png", account, 0.9, True)

    return all_in_lobby

  async def execute(self, ctx: context.Context):
    from states.make_lobbies.make_lobbies import MakeLobbies
    from states.select_map import SelectMap

    await asyncio.sleep(self.delay)

    launched_accounts = WindowService.scan_cs2_windows(ctx.accounts(), values=True)

    if self.game_schema is None:
      preset_applied = False
      if launched_accounts:
        new_schema = ctx.presets.get_schema_for_launched_accounts(launched_accounts)
        if new_schema:
          self.game_schema = new_schema
          preset_applied = True

      if not preset_applied:
        self.game_schema = generate_party_schema(
          launched_accounts, ctx.settings.system.farm_mode
        )

    show_must_go_on = False

    accounts = [account for party in self.game_schema for account in party.all]

    # Завершение фарма в определенное время, эво пора на работу
    if ctx.settings.user.farm_until:
      try:
        now = datetime.datetime.now()
        t = datetime.datetime.strptime(ctx.settings.user.farm_until, "%H:%M").time()
        target_min = t.hour * 60 + t.minute
        now_min = now.hour * 60 + now.minute
        if 0 <= (now_min - target_min) % 1440 <= 120:
          for account in accounts:
            account.stop_account(ctx)
          return states.Idle()
      except ValueError:
        pass

    for account in accounts:
      logger.info(f"account: {account.login} is {account.lock.status}")
      if account.lock.status == FarmStatus.NEED_TO_FARM:
        show_must_go_on = True
        break

    if not show_must_go_on and ctx.settings.user.overfarm is not None:
      show_must_go_on = True
      for account in accounts:
        account_xp = account.lock.xp or 0
        if (
          account_xp >= ctx.settings.user.overfarm
          and account.lock.status != FarmStatus.NEED_TO_FARM
        ):
          show_must_go_on = False
          break

    logger.info(f"show_must_go_on: {show_must_go_on}")
    if show_must_go_on:
      logger.info(f"Checking lobbies for {len(launched_accounts)} launched accounts")
      all_lobbies = await self.check_if_all_in_lobby(launched_accounts)
      logger.info(f"All lobbies check result: {all_lobbies}")
      if all_lobbies:
        return SelectMap(self.game_schema)
      else:
        for account in accounts:
          await CS2Controller.move_mouse_async(
            **game_constants.open_side_bar, account=account
          )

          await asyncio.sleep(0.3)

          await CS2Controller.click_if_exists_async("img/exit.png", account, 0.9, True)

          await asyncio.sleep(0.3)

        return MakeLobbies(self.game_schema)
    else:
      return StartUnfarmed(self.game_schema)
