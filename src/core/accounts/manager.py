import json
from typing import Dict, List, Set
from .model import Account, RunningAccount

from src.core.logging import get_logger

logger = get_logger("accounts")

ACCOUNTS_FILE = "accounts.json"


class Accounts:
  accounts: Dict[str, Account] = {}
  running: List[RunningAccount] = []

  def __init__(
    self, accounts: Dict[str, Account], running: List[RunningAccount]
  ):
    self.accounts = accounts
    self.running = running
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

    return Accounts(accounts, [])

  def select(self, login: str):
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