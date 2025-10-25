import asyncio
from dataclasses import dataclass, field

from src.ui.widgets import Button
from src.core.panel import Message, State, StateManager, handles
from src.core.context import Context
from src.core.account import Account
from src.core.logging import get_logger

from states import LaunchAccounts, LootAccounts

logger = get_logger("state.idle")


@dataclass
class StartFarm(Message):
  accounts: list[Account] = field(default_factory=list)


@dataclass
class StartLoot(Message):
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
        on_click=acquire_accounts(StartFarm),
        tooltip="Starts the farming process for all selected accounts.",
      ),
      Button(
        "Loot Selected",
        on_click=acquire_accounts(StartLoot),
        tooltip="Background loot of selected accounts.",
      ),
    ]

  async def execute(self, ctx: Context):
    while True:
      await asyncio.sleep(1)

  @handles(StartFarm)
  async def _on_start_farming(self, manager: StateManager, message: StartFarm):
    logger.debug(f"start farming with {message.accounts}")
    await manager.into_state(LaunchAccounts(message.accounts))

  @handles(StartLoot)
  async def _on_start_looting(self, manager: StateManager, message: StartFarm):
    logger.debug(f"start looting with {message.accounts}")
    await manager.into_state(LootAccounts(message.accounts))
