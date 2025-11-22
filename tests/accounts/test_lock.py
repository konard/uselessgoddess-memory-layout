import pytest
from core.account.model import Account
from core.account.lock import AccountsLock


def test_accounts_lock_creation(tmp_path):
  lock_file = tmp_path / "accounts.lock"
  lock = AccountsLock(lock_file)

  assert isinstance(lock, AccountsLock)
  assert lock_file.exists()


def test_set_and_get_account_info(tmp_path):
  lock_file = tmp_path / "accounts.lock"
  lock = AccountsLock(lock_file)
  login = "test_user"

  lock.set_account_info(login, lvl=10, xp=1500, invite="INV123")
  info = lock.get_account_info(login)

  assert info is not None
  assert info.get("lvl") == 10
  assert info.get("xp") == 1500
  assert info.get("invite") == "INV123"


def test_account_model_integration(tmp_path):
  lock_file = tmp_path / "accounts.lock"
  lock = AccountsLock(lock_file)

  account = Account(
    login="test_acc",
    password="pass123",
    shared_secret="secret123",
    identity_secret="identity123",
    steam_id="123456789",
  )

  account.update_from_lock(lock)

  account.lock.lvl = 30
  account.lock.xp = 5000
  account.lock.invite = "INV789"

  assert account.lock.lvl == 30

  info = lock.get_account_info("test_acc")
  assert info.get("lvl") == 30
  assert info.get("xp") == 5000
