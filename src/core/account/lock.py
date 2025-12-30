from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from tinydb import Query, TinyDB

from core.logging import get_logger
from core.security import EncryptedJSONStorage

logger = get_logger("account.lock")


class AccountsLock:
  def __init__(self, db_path: Path | str = "data/accounts.lock") -> None:
    self._db_path = Path(db_path)
    if not os.path.isfile(db_path):
      with open(db_path, "w") as file:
        file.write("{}")

    self._migrate_if_plaintext()

    self._db = TinyDB(str(self._db_path), storage=EncryptedJSONStorage)
    self._table = self._db.table("accounts")
    self._query = Query()

  def _migrate_if_plaintext(self) -> None:
    if not self._db_path.exists():
      return
    logger.trace("migrating from plain test")

    try:
      with open(self._db_path, encoding="utf-8") as f:
        content = f.read().strip()

      if not content:
        return

      data = json.loads(content)

      logger.warn(
        f"Detected plaintext storage at {self._db_path}. Migrating to encrypted storage"
      )

      storage = EncryptedJSONStorage(str(self._db_path))
      storage.write(data)
      logger.info("Storage migration completed successfully.")

    except (UnicodeDecodeError, json.JSONDecodeError):
      logger.debug("storage appears to be encrypted already.")
    except Exception as e:
      logger.error(f"error during storage migration check: {e}")

  def get_account_info(self, login: str) -> dict[str, Any] | None:
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
    with contextlib.suppress(Exception):
      self.close()
