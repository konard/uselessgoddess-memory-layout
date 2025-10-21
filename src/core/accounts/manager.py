import json
from typing import Dict, List
from .model import Account, RunningAccount

from src.core.logging import get_logger

logger = get_logger("yacs.accounts")


class Accounts:
  accounts: Dict[str, Account] = {}
  running: List[RunningAccount] = []

  def __init__(self, accounts: Dict[str, Account], running: List[RunningAccount]):
    self.accounts = accounts
    self.running = running

  @staticmethod
  def load(file: str = "accounts.json"):
    accounts: Dict[str, Account] = {}
    try:
      with open(file, "r") as f:
        accounts_data = json.load(f)
        for login, data in accounts_data.items():
          accounts[login] = Account.from_json(data)
        logger.debug(f"loaded {len(accounts)} accounts.")
    except FileNotFoundError:
      logger.error(f"Accounts file not found: {file}")
    except json.JSONDecodeError:
      logger.error(f"Invalid accountsfile: {file}")
    
    return Accounts(accounts, [])
