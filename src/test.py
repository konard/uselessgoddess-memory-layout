import json
from typing import Dict

from core.account.model import Account
from core.services.windows_service import WindowService


def test_scan_cs2_windows():
  """Тестовая функция для scan_cs2_windows"""
  # Загружаем accounts.json
  with open("accounts.json", "r", encoding="utf-8") as f:
    accounts_data = json.load(f)

  # Создаем словарь Account объектов
  accounts: Dict[str, Account] = {}
  for login, data in accounts_data.items():
    accounts[login] = Account.from_json(data)

  print(f"Загружено {len(accounts)} аккаунтов из accounts.json")
  print(f"Аккаунты: {list(accounts.keys())}\n")

  # Вызываем scan_cs2_windows
  print("Сканируем окна CS2...")
  running_accounts = WindowService.scan_cs2_windows(accounts)

  # Выводим результаты
  print(f"\nНайдено запущенных окон: {len(running_accounts)}")
  print("-" * 80)

  if running_accounts:
    for login, running_acc in running_accounts.items():
      print(f"Логин: {login}")
      print(f"  Позиция: ({running_acc.posX}, {running_acc.posY})")
      print(f"  PID: {running_acc.runner_pid}")
      print(f"  Заголовок окна: {running_acc.win_cs_title}")
      print(f"  Steam ID: {running_acc.steam_id}")
      print()
  else:
    print("Запущенных окон CS2 не найдено")
    print("Убедитесь, что:")
    print("  1. CS2 запущен")
    print("  2. Заголовок окна имеет формат: [login] # CS")


if __name__ == "__main__":
  test_scan_cs2_windows()
