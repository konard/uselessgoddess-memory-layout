import asyncio
from typing import Optional, Tuple
from core.account.model import Account
from core.panel import State
from core.context import Context
from core.logging import get_logger
from core.services.cs_controller import CS2Controller
from core.services.gc.lobby_service import EventNames
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
from core import game_constants
from states.select_accounts import SelectAccounts
from states.types import PartySchema
from utils.friend_code_generator import generate_friend_code
from .generate_party_schema import generate_party_schema
from ui.widgets import Progress

logger = get_logger("state.farm")


farm_mode_size = {
  FarmMode.TWO_BY_TWO: 4,
  FarmMode.FIVE_BY_FIVE: 10,
}


class MakeLobbies(State):
  def __init__(self, party_schema: Optional[Tuple[PartySchema, PartySchema]]):
    self.party_schema: Optional[Tuple[PartySchema, PartySchema]] = party_schema

  def layout(self, ctx: Context, dispatch):
    self.progress = Progress()

    return [self.progress]

  async def accept_invite(self, ctx: Context, account: Account):
    await ctx.gc.lobby_service.wait_for_invite(account)

    WindowService.focus_window(account.win_cs_title)
    await asyncio.sleep(1)
    CS2Controller.move_mouse(**game_constants.open_side_bar, account=account)
    await asyncio.sleep(0.5)
    CS2Controller.click(**game_constants.accept_invite, account=account)
    await asyncio.sleep(0.5)

    await ctx.gc.lobby_service.event_service.wait_for_event(
      account, EventNames.INVITE_RECEIVED, timeout=10
    )

  async def execute(self, ctx: Context):
    from states.select_map import SelectMap

    launched_accounts = WindowService.scan_cs2_windows(ctx.accounts())
    farm_mode = ctx.settings.system.farm_mode

    if farm_mode_size.get(farm_mode) != len(launched_accounts):
      return SelectAccounts(farm_mode_size[farm_mode]).then(self)

    try:
      if self.party_schema is None:
        self.party_schema = generate_party_schema(launched_accounts, farm_mode)

      for party in self.party_schema:
        await WindowService.focus_window_async(party.leader.win_cs_title)
        await CS2Controller.move_mouse_async(
          **game_constants.invite_friend, account=party.leader
        )
        await asyncio.sleep(1)
        await CS2Controller.click_async(
          **game_constants.invite_friend, account=party.leader, immediate=True
        )

        await CS2Controller.click_async(
          **game_constants.friend_code_input, account=party.leader
        )

        i = 0
        while i < len(party.members):
          member = party.members[i]
          await CS2Controller.copy_to_clipboard_async(
            generate_friend_code(member.steam_id)
          )
          await CS2Controller.paste_from_clipboard_async()
          await CS2Controller.click_async(
            **game_constants.result_button, account=party.leader
          )
          await asyncio.sleep(1)
          await CS2Controller.click_if_exists_async(
            "img/invite.png", party.leader, 0.9, True
          )

          try:
            await self.accept_invite(ctx, member)

          except Exception as e:
            logger.error(f"Error accepting invite for {member.login}: {e}")
            await WindowService.focus_window_async(party.leader.win_cs_title)
            await asyncio.sleep(1)
            await CS2Controller.press_escape_async()
            await asyncio.sleep(0.3)
            await CS2Controller.press_escape_async()
            await asyncio.sleep(0.3)

            await CS2Controller.move_mouse_async(
              **game_constants.invite_friend, account=party.leader
            )
            await asyncio.sleep(1)
            await CS2Controller.click_async(
              **game_constants.invite_friend,
              account=party.leader,
              immediate=True,
            )

            await CS2Controller.click_async(
              **game_constants.friend_code_input, account=party.leader
            )
            continue

          i += 1

        print(f"party {party.leader.login} lobbied")

        await asyncio.sleep(0.3)
        await WindowService.focus_window_async(party.leader.win_cs_title)

        await CS2Controller.click_async(
          **game_constants.open_side_bar, account=party.leader
        )
        await asyncio.sleep(1)
        await CS2Controller.press_escape_async()
        await asyncio.sleep(0.3)
        await CS2Controller.press_escape_async()
        await asyncio.sleep(0.3)

      await asyncio.sleep(0.5)
      return SelectMap(self.party_schema)

    except ValueError as e:
      logger.error(f"{e}")
      return
