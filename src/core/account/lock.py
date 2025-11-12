from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Any
from tinydb import TinyDB, Query
from core.logging import get_logger


logger = get_logger("account.lock")


class AccountsLock:
  def __init__(self, db_path: Path | str) -> None:
    self._db_path = Path(db_path)
    self._db = TinyDB(str(self._db_path))
    self._table = self._db.table("accounts")
    self._query = Query()

  def get_account_info(self, login: str) -> Dict[str, Any] | None:
    result = self._table.get(self._query.login == login)
    if result:
      return {k: v for k, v in result.items() if k != "login"}
    return None

  def set_account_info(self, login: str, **kwargs: Any) -> None:
    account_data = {"login": login}
    account_data.update(kwargs)

    existing = self._table.get(self._query.login == login)
    if existing:
      self._table.update(account_data, self._query.login == login)
    else:
      self._table.insert(account_data)

    logger.debug(f"Updated account info for {login}: {kwargs}")

  def get_field(self, login: str, field_name: str) -> Any:
    info = self.get_account_info(login)
    return info.get(field_name) if info else None

  def set_field(self, login: str, field_name: str, value: Any) -> None:
    kwargs = {field_name: value}
    self.set_account_info(login, **kwargs)

  def close(self) -> None:
    if hasattr(self, "_db") and self._db is not None:
      self._db.close()

  def __del__(self) -> None:
    try:
      self.close()
    except Exception:
      pass
