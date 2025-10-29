from typing import List
from core.logging import get_logger
from core.services.gc import GCService

from .account import Account
from .services import AccountsService, SettingsService


logger = get_logger("ctx")

class Context:
  account: AccountsService
  settings: SettingsService
  gc: GCService
  
  def __init__(self):
    self.account = AccountsService.load()
    self.settings = SettingsService()
    self.gc = GCService()
    
  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())
