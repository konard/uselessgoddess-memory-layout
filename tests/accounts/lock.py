import os
import tempfile
import unittest
from pathlib import Path
from src.core.account.model import Account
from src.core.account.lock import AccountsLock


class TestAccountsLock(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()
    self.file = Path(self.temp_dir) / "accounts.lock"

  def tearDown(self):
    if self.file.exists():
      self.file.unlink()
    os.rmdir(self.temp_dir)

  def test_accounts_lock_creation(self):
    lock = AccountsLock(self.file)
    self.assertIsInstance(lock, AccountsLock)
    self.assertTrue(self.file.exists())

  def test_set_and_get_account_info(self):
    lock = AccountsLock(self.file)

    login = "test_user"
    lock.set_account_info(login, lvl=10, xp=1500, invite="INV123")

    info = lock.get_account_info(login)

    self.assertIsNotNone(info)
    self.assertEqual(info.get("lvl"), 10)
    self.assertEqual(info.get("xp"), 1500)
    self.assertEqual(info.get("invite"), "INV123")

  def test_account_model_integration(self):
    lock = AccountsLock(self.file)

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

    self.assertEqual(account.lock.lvl, 30)
    self.assertEqual(account.lock.xp, 5000)
    self.assertEqual(account.lock.invite, "INV789")

    info = lock.get_account_info("test_acc")
    self.assertEqual(info.get("lvl"), 30)
    self.assertEqual(info.get("xp"), 5000)
    self.assertEqual(info.get("invite"), "INV789")

  def test_property_access(self):
    lock = AccountsLock(self.file)

    account = Account(
      login="prop_test",
      password="pass123",
      shared_secret="secret123",
      identity_secret="identity123",
      steam_id="987654321",
    )

    lock.set_account_info("prop_test", lvl=15, xp=2500, invite="INV000")

    account.update_from_lock(lock)

    self.assertEqual(account.lock.lvl, 15)
    self.assertEqual(account.lock.xp, 2500)
    self.assertEqual(account.lock.invite, "INV000")
