from typing import List
from core.logging import get_logger

from .account import Account
from .services import AccountsService, SettingsService


logger = get_logger("ctx")


class Context:
  account: AccountsService
  settings: SettingsService

  def __init__(self):
    self.account = AccountsService.load()
    self.settings = SettingsService()

  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())
