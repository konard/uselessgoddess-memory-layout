from core import context
from core.account.model import FarmStatus
from core.logging import get_logger
from core.panel import state
from states.types import GameSchema

logger = get_logger("state.continue_farm")


class ContinueFarm(state):
  def __init__(self, game_schema: GameSchema):
    self.game_schema = game_schema

  async def execute(self, ctx: context):
    show_must_go_on = False

    for party in self.game_schema:
      for account in party.all:
        if account.lock.status == FarmStatus.NEED_TO_FARM:
          show_must_go_on = True
          break

    print(show_must_go_on)
    logger.info("ContinueFarm state")
