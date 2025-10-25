from typing import List
from core.logging import get_logger

from .account import Account
from .services import AccountsService


logger = get_logger("ctx")


class Context:
  account: AccountsService

  def __init__(self):
    self.account = AccountsService.load()

  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())
