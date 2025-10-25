import json
import asyncio
from typing import Dict, List, Set

from core.account import Account, RunningAccount
from core.logging import get_logger
\

logger = get_logger("sv.accounts")

ACCOUNTS_FILE = "accounts.json"


class AccountsService:
  accounts: Dict[str, Account] = {}

  def __init__(self, accounts: Dict[str, Account]):
    self.accounts = accounts
    self._selected: Set[str] = set()

  @staticmethod
  def load(file: str = "accounts.json"):
    accounts: Dict[str, Account] = {}
    try:
      with open(file, "r") as f:
        accounts_data = json.load(f)
        for login, data in accounts_data.items():
          accounts[login] = Account.from_json(data)
        logger.info(f"loaded {len(accounts)} accounts.")
    except FileNotFoundError:
      logger.error(f"Accounts file not found: {file}")
    except json.JSONDecodeError:
      logger.error(f"Invalid accountsfile: {file}")

    return AccountsService(accounts)

  def select(self, login: str):
    logger.info(f"select {login}")
    if login in self.accounts:
      self._selected.add(login)
      logger.trace(f"account selected: {login}")

  def deselect(self, login: str):
    self._selected.discard(login)
    logger.trace(f"account deselected: {login}")

  # TODO!: maybe use `class Select` to manage selection
  def selected(self) -> List[Account]:
    accounts = [
      self.accounts[login] for login in self._selected if login in self.accounts
    ]
    return accounts

  def capture_selected(self) -> List[Account]:
    accounts = self.selected()
    logger.trace(f"acquire selected accounts: {accounts}")
    self._selected.clear()
    return accounts

  async def stop_account_processes(self, logins: List[str]):
    logger.warn(
      f"Process stopping is not yet implemented. Requested for: {logins}"
    )
    await asyncio.sleep(1)
