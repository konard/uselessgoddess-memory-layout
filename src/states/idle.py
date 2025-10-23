import asyncio
from dataclasses import dataclass, field

from src.ui import Button
from src.core.panel import Message, State, StateManager, handles
from src.core.context import Context
from src.core.accounts import Account
from src.core.logging import get_logger

from states import LaunchAccounts

logger = get_logger("state.idle")


@dataclass
class StartFarming(Message):
  accounts: list[Account] = field(default_factory=list)


class Idle(State):
  def layout(self, ctx: Context, dispatch):
    def acquire_accounts():
      # TODO!: maybe rethink dispatch propogation
      return dispatch(StartFarming(ctx.account.capture_selected()))

    return [
      Button(
        "Start Farming",
        on_click=acquire_accounts,
        tooltip="Starts the farming process for all selected accounts.",
      )
    ]

  async def execute(self, ctx: Context):
    while True:
      await asyncio.sleep(1)

  @handles(StartFarming)
  async def _on_start_farming(
    self, manager: StateManager, message: StartFarming
  ):
    logger.debug(f"start farming with {message.accounts}")
    await manager.into_state(LaunchAccounts(message.accounts))
