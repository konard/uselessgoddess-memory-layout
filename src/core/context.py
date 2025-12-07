from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING
from core.logging import get_logger
from core.services import (
  SRTService,
  ScreenCaptureService,
  ai,
  UIService,
  WindowService,
  GSIService,
  GCService,
)
from core.account import FarmStatus

from .account import Account
from .services import AccountsService, SettingsService

if TYPE_CHECKING:  # allow recursive ctx usage
  from core.services.bot import TelegramBotService

logger = get_logger("ctx")


class Context:
  account: AccountsService
  settings: SettingsService
  srt: SRTService
  bot: TelegramBotService
  ui: UIService
  ai: ai.InferenceService
  screen: ScreenCaptureService
  gc: GCService

  def __init__(self):
    from core.services.bot import TelegramBotService

    self.account = AccountsService.load()
    self.settings = SettingsService()
    self.srt = SRTService()
    self.bot = TelegramBotService(self)
    self.ui = UIService()
    self.ai = ai.InferenceService(
      "model.onnx",
      ["ct", "t"],  # TODO: STRICT CONSTANT
    )  # TODO: make prebuilt configurable
    self.screen = ScreenCaptureService()
    self.gsi = GSIService(port=6969)  # TODO: avoid hardcoded ports
    self.gc = GCService(self)

  def accounts(self) -> List[Account]:
    return sorted(list(self.account.accounts.values()), key=lambda x: x.login)

  def unfarmed_accounts(self) -> List[Account]:
    launched_accounts = WindowService.scan_cs2_windows(
      self.accounts(), values=False
    )
    accounts = self.accounts()
    unfarmed_accounts_list = filter(
      lambda x: x.lock.status == FarmStatus.NEED_TO_FARM
      and x.login not in launched_accounts,
      accounts,
    )
    return list(unfarmed_accounts_list)

  @property
  def launched_accounts(self) -> List[Account]:
    return WindowService.scan_cs2_windows(self.accounts(), values=True)

  @property  # shorthand to `settings`
  def s(self):
    return self.settings

  @property  # shorthand to `settings.user`
  def su(self):
    return self.settings.user

  @property  # shorthand to `settings.system`
  def ss(self):
    return self.settings.system

  def window_size(self) -> Tuple[int, int]:
    return self.su.win_w, self.su.win_h

  async def send_message(self, text: str, image=None):
    for chat_id in self.su.telegram_whitelist:
      await self.bot.send_message(chat_id, text, image)
