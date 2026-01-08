from __future__ import annotations

from typing import TYPE_CHECKING

from core.account import FarmStatus
from core.logging import get_logger
from core.services import (
  GCService,
  GSIService,
  LicenseService,
  MetricsService,
  PresetsService,
  ScreenCaptureService,
  SRTService,
  UIService,
  WindowService,
  ai,
)

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
  lic: LicenseService
  presets: PresetsService
  metrics: MetricsService

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
      self.settings.user.advanced.inference_device,
      self.settings.user.advanced.inference_threads,
    )  # TODO: make prebuilt configurable
    self.screen = ScreenCaptureService()
    self.gsi = GSIService(port=6969)  # TODO: avoid hardcoded ports
    self.gc = GCService(self)
    self.lic = LicenseService(self.settings.user)
    self.presets = PresetsService()
    self.metrics = MetricsService(self.lic)
    self.blacklisted_accounts: set[str] = set()

  def accounts(self) -> list[Account]:
    return sorted(
      self.account.accounts.values(),
      key=lambda x: 0 if x.lock.lvl is None else x.lock.lvl,
    )

  def unfarmed_accounts(self) -> list[Account]:
    launched_accounts = WindowService.scan_cs2_windows(self.accounts(), values=False)
    accounts = self.accounts()
    unfarmed_accounts_list = filter(
      lambda x: x.lock.status == FarmStatus.NEED_TO_FARM
      and x.login not in launched_accounts,
      accounts,
    )
    return list(unfarmed_accounts_list)

  @property
  def launched_accounts(self) -> list[Account]:
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

  def window_size(self) -> tuple[int, int]:
    return self.su.win_w, self.su.win_h

  async def send_message(self, text: str, image=None):
    for chat_id in self.su.telegram_whitelist:
      await self.bot.send_message(chat_id, text, image)
