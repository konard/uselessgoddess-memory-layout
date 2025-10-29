import asyncio
from dataclasses import dataclass, field

from ui.widgets import Button
from core.context import Context
from core.account import Account
from core.logging import get_logger
from core.panel import Message, State, StateManager, handles
from states.wait_for_game import WaitForGame

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


class Idle(State):
  def layout(self, ctx: Context, dispatch):
    def acquire_accounts(mtype):
      def inner():
        accounts = ctx.account.capture_selected()
        # TODO!: maybe rethink dispatch propogation
        if not accounts:
          logger.info("Please select at least one account")
        else:
          dispatch(mtype(accounts))

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
      Button(
        "Send Trade Selected",
        on_click=acquire_accounts(Trade),
        tooltip="Trade inventory to trade url.",
      ),
      Button(
        "Wait for Game",
        on_click=acquire_accounts(WaitForGame),
        tooltip="Wait for game to start.",
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
    if not manager.context.settings.user.trade_url:
      logger.error("You must set `trade_url` in settings to send loot")
      return

    logger.debug(f"send trades of {message.accounts}")
    await manager.into_state(
      states.TradeAccounts(message.accounts).then(self),
    )

  @handles(WaitForGame)
  async def _on_wait_for_game(
    self, message: WaitForGame, manager: StateManager
  ):
    logger.debug(f"wait for game {message.accounts}")
    await manager.into_state(
      states.WaitForGame(message.accounts).then(self),
    )
