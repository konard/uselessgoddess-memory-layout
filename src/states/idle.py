import asyncio
from dataclasses import dataclass, field

from ui import ButtonType
from states.select_map import SelectMap
from ui.widgets import Button, HStack

from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.panel import Message, State, StateManager, handles

from states import (
  debug,
  MatchState,
  MakeLobbies,
  WaitForGame,
  LaunchAccounts,
)

import states

logger = get_logger("state.idle")


@dataclass
class Farm(Message):
  accounts: list[Account] = field(default_factory=list)


@dataclass
class Loot(Message):
  accounts: list[Account] = field(default_factory=list)


@dataclass
class Trade(Message):
  accounts: list[Account] = field(default_factory=list)


@dataclass
class Report(Message):
  accounts: list[Account] = field(default_factory=list)


class Idle(State):
  def layout(self, ctx: Context, dispatch):
    def acquire_accounts(mtype):
      def inner():
        logins = ctx.ui.capture_selected()
        accounts = [
          ctx.account.accounts[login]
          for login in logins
          if login in ctx.account.accounts
        ]
        # TODO!: maybe rethink dispatch propogation
        if not accounts:
          logger.info("Please select at least one account")
        else:
          dispatch(mtype(accounts))

      return inner

    def acquire_running(mtype):
      def inner():
        from core.services import WindowService

        accounts = WindowService.scan_cs2_windows(ctx.accounts())
        dispatch(mtype(accounts))

      return inner

    def launch(mtype):
      def inner():
        dispatch(mtype())

      return inner

    return [
      Button(
        "Start Farming",
        on_click=acquire_accounts(Farm),
        tooltip="Starts farming for all selected accounts.",
      ),
      Button(
        "Loot Selected",
        on_click=acquire_accounts(Loot),
        tooltip="Loot weakly drop of selected accounts.",
      ),
      HStack(
        Button(
          "Trade accounts",
          on_click=acquire_accounts(Trade),
          tooltip="Trade inventories to trade url.",
        ),
        Button(
          "Drop report",
          on_click=acquire_accounts(Trade),
          tooltip="Make drop report.",
        ),
      ),
      Button(
        "Wait for Game",
        on_click=launch(WaitForGame),
        tooltip="Wait for game to start.",
      ),
      Button(
        "Launch Accounts",
        on_click=acquire_accounts(LaunchAccounts),
        tooltip="Launch accounts.",
      ),
      Button(
        "Start match",
        on_click=acquire_running(MatchState),
        button_type=ButtonType.SPECIAL,
        tooltip="Manually run auto-match",
      ),
      Button(
        "Debug AI (Camera)",
        on_click=lambda: dispatch(debug.AIState()),
        button_type=ButtonType.SPECIAL,
        tooltip="Open OpenCV window to see what bot sees",
      ),
      Button(
        "Make Lobbies",
        on_click=lambda: dispatch(MakeLobbies()),
        tooltip="Make lobbies.",
      ),
      Button(
        "Select Map",
        on_click=lambda: dispatch(SelectMap()),
        tooltip="Select map.",
      ),
    ]

  async def execute(self, ctx: Context):
    while True:
      await asyncio.sleep(1)

  @handles(Farm)
  async def _on_start_farm(self, message: Farm, manager: StateManager):
    logger.debug(f"start farming {message.accounts}")
    await manager.into_state(
      states.LaunchAccounts(message.accounts).then(self),
    )

  @handles(Loot)
  async def _on_loot(self, message: Loot, manager: StateManager):
    logger.debug(f"loot {message.accounts}")
    await manager.into_state(
      states.LootAccounts(message.accounts).then(self),
    )

  @handles(Trade)
  async def _on_trade(self, message: Trade, manager: StateManager):
    logger.debug(f"send trades {message.accounts}")
    await manager.into_state(
      states.ScanAccounts(message.accounts, trade=True).then(self),
    )

  @handles(Trade)
  async def _on_report(self, message: Report, manager: StateManager):
    logger.debug(f"report drop {message.accounts}")
    await manager.into_state(
      states.ScanAccounts(message.accounts, trade=False).then(self),
    )

  @handles(WaitForGame)
  async def _on_wait_for_game(
    self, message: WaitForGame, manager: StateManager
  ):
    logger.debug(f"wait for game {message.accounts}")
    await manager.into_state(
      states.WaitForGame(message.accounts).then(self),
    )

  @handles(LaunchAccounts)
  async def _on_launch_accounts(
    self, message: LaunchAccounts, manager: StateManager
  ):
    logger.debug(f"launch accounts {message.accounts_to_launch}")
    await manager.into_state(
      states.LaunchAccounts(message.accounts_to_launch).then(self),
    )

  @handles(MatchState)
  async def _on_match(self, state, manager: StateManager):
    logger.debug(f"start match: {state}")
    await manager.into_state(state.then(self))

  @handles(debug.AIState)
  async def _on_debug_ai(self, state, manager: StateManager):
    await manager.into_state(state.then(self))

  @handles(MakeLobbies)
  async def _on_make_lobbies(self, state, manager: StateManager):
    await manager.into_state(
      state.then(self),
    )

  @handles(SelectMap)
  async def _on_select_map(self, state, manager: StateManager):
    await manager.into_state(
      state.then(self),
    )
