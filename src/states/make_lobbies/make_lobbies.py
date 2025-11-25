import asyncio
from core.account.model import Account
from core.panel import State
from core.context import Context
from core.logging import get_logger
from core.services.cs_controller import CS2Controller
from core.services.settings import FarmMode
from core.services.windows_service import WindowService
from resources import game_constants
from states.select_accounts import SelectAccounts
from utils.friend_code_generator import generate_friend_code
from .generate_party_schema import generate_party_schema
from ui.widgets import Progress

logger = get_logger("state.farm")


farm_mode_size = {
  FarmMode.TWO_BY_TWO: 4,
  FarmMode.FIVE_BY_FIVE: 10,
}


class MakeLobbies(State):
  def __init__(self):
    pass

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

  async def execute(self, ctx: Context):
    launched_accounts = WindowService.scan_cs2_windows(ctx.accounts())
    farm_mode = ctx.settings.system.farm_mode

    print(launched_accounts, farm_mode)

    if farm_mode_size.get(farm_mode) != len(launched_accounts):
      return SelectAccounts(farm_mode_size[farm_mode]).then(self)

    try:
      party_schema = generate_party_schema(launched_accounts, farm_mode)

      print(game_constants)
      for party in party_schema:
        WindowService.focus_window(party.leader.win_cs_title)
        CS2Controller.move_mouse(
          **game_constants.invite_friend, account=party.leader
        )
        await asyncio.sleep(1)
        CS2Controller.click(
          **game_constants.invite_friend, account=party.leader, immediate=True
        )

        CS2Controller.click(
          **game_constants.friend_code_input, account=party.leader
        )

        for member in party.members:
          CS2Controller.copy_to_clipboard(generate_friend_code(member.steam_id))
          CS2Controller.paste_from_clipboard()
          CS2Controller.click(
            **game_constants.result_button, account=party.leader
          )
          await asyncio.sleep(1)
          CS2Controller.click_if_exists(
            "resources/img/invite.png", party.leader, 0.9, True
          )

        await asyncio.sleep(0.3)
        WindowService.focus_window(party.leader.win_cs_title)
        await asyncio.sleep(0.3)
        CS2Controller.press_escape()

        for member in party.members:
          await self.accept_invite(ctx, member)

    except ValueError as e:
      reason: str = e.reason
      return

    logger.info("all lobbies made")
