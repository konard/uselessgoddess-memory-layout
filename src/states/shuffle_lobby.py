import asyncio
from sre_parse import State
from typing import Optional, Tuple
from core import game_constants, utils
from core.context import Context
from core.services.cs_controller import CS2Controller
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
from core.services.launch_service import LaunchService
from core.logging import get_logger
import states
from states.types import PartySchema

logger = get_logger("state.shuffle")


class ShuffleLobby(State):
  def __init__(
    self,
    party_schema: Tuple[PartySchema, PartySchema],
    retries: Optional[int] = None,
  ):
    self.party_schema: Tuple[PartySchema, PartySchema] = party_schema
    self.retries = retries

  async def execute(self, ctx: Context):
    if self.retries > ctx.su.times_to_brute_force:
      logger.info("Shuffle limit reached.")

      # Check if current accounts belong to a preset
      current_leader = self.party_schema[0].leader
      preset_name = ctx.presets.get_preset_by_account(current_leader.login)

      if preset_name:
        logger.info(
          f"Current accounts belong to preset '{preset_name}'. Marking as error."
        )
        ctx.presets.mark_preset_error(preset_name)

        next_preset = ctx.presets.get_next_available_preset(ctx)

        if next_preset:
          logger.info(f"Switching to next preset: '{next_preset.name}'")

          # Stop all currently running accounts
          for party in self.party_schema:
            for acc in party.all:
              if acc.stop_account(ctx.su):
                logger.info(f"Stopped {acc.login}")
              else:
                logger.warn(f"Failed to stop {acc.login}")

          # Get Account objects for the next preset
          new_accounts = []
          for login in next_preset.accounts:
            if login in ctx.account.accounts:
              new_accounts.append(ctx.account.accounts[login])
            else:
              logger.error(
                f"Account {login} from preset {next_preset.name} not found in accounts service"
              )

          if new_accounts:
            return states.LaunchAccounts(new_accounts).then(
              states.MakeLobbies(None)
            )
          else:
            logger.error("No valid accounts found for next preset")
        else:
          logger.info("No next available preset found.")

      logger.info("Swapping single account...")

      # Candidate to stop: last member of the second party
      victim = (
        self.party_schema[1].members[-1]
        if self.party_schema[1].members
        else self.party_schema[1].leader
      )

      unfarmed = ctx.unfarmed_accounts()

      unfarmed = list(
        filter(lambda x: x.login not in ctx.blacklisted_accounts, unfarmed)
      )

      if not unfarmed:
        raise Exception(
          "Failed to shuffle lobby: no unfarmed accounts available for swap"
        )

      replacement = unfarmed[0]
      logger.info(f"Swapping {victim.login} with {replacement.login}")

      ctx.blacklisted_accounts.add(victim.login)

      if victim.stop_account(ctx.su):
        logger.info(f"Stopped {victim.login}")
      else:
        logger.warn(f"Failed to stop {victim.login}, might be already stopped")

      res = await utils.block_on(LaunchService.launch_account_with_steam)(
        replacement, ctx.su, ctx.accounts()
      )

      if not res:
        raise Exception(
          f"Failed to launch replacement account {replacement.login}"
        )

      logger.info(f"Launched {replacement.login}")

      for party in self.party_schema:
        for account in party.all:
          await WindowService.focus_window_async(account.win_cs_title)
          await asyncio.sleep(0.3)
          await CS2Controller.move_mouse_async(
            **game_constants.open_side_bar, account=account
          )
          await asyncio.sleep(0.3)
          await CS2Controller.click_if_exists_async(
            "img/exit.png", account, 0.9
          )
          await asyncio.sleep(0.3)

      return states.MakeLobbies(None)

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
        await CS2Controller.move_mouse_async(
          **game_constants.open_side_bar, account=account
        )
        await asyncio.sleep(0.3)
        await CS2Controller.click_if_exists_async("img/exit.png", account, 0.9)
        await asyncio.sleep(0.3)

    return states.MakeLobbies(new_party_schema, self.retries)
