from __future__ import annotations
from typing import List, TYPE_CHECKING
from core.logging import get_logger
from core.services import GCService
from core.services import SRTService
from core.services import ai

from .account import Account
from .services import AccountsService, SettingsService

if TYPE_CHECKING:  # allow recursive ctx usage
  from core.services.bot import TelegramBotService

logger = get_logger("ctx")


class Context:
  account: AccountsService
  settings: SettingsService
  gc: GCService
  srt: SRTService
  bot: TelegramBotService

  ai: ai.InferenceService

  def __init__(self):
    from core.services.bot import TelegramBotService

    self.account = AccountsService.load()
    self.settings = SettingsService()
    self.gc = GCService()
    self.srt = SRTService()
    self.bot = TelegramBotService(self)
    self.ai = ai.InferenceService(
      "resources/model.onnx",
      ["ct", "t"],  # TODO: STRICT CONSTANT
    )  # TODO: make prebuilt configurable

  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())

  @property  # shorthand to `settings`
  def s(self):
    return self.settings

  @property  # shorthand to `settings.user`
  def su(self):
    return self.settings.user
