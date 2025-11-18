from typing import List
from core.logging import get_logger
from core.services import GCService
from core.services import SRTService

from .account import Account
from .services import AccountsService, SettingsService


logger = get_logger("ctx")


class Context:
  account: AccountsService
  settings: SettingsService
  gc: GCService
  srt: SRTService

  def __init__(self):
    self.account = AccountsService.load()
    self.settings = SettingsService()
    self.gc = GCService()
    self.srt = SRTService()

  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())

  @property  # shorthand to `settings`
  def s(self):
    return self.settings
