from typing import List
from core.logging import get_logger

from .accounts import Accounts, Account


logger = get_logger("yacs.ctx")


class Context:
  account: Accounts

  def __init__(self):
    self.account = Accounts.load()

  def accounts(self) -> List[Account]:
    return list(self.account.accounts.values())
