"""
Простая утилита для чтения бинарных файлов.

Использование:
    python scripts/read_bin.py <путь_к_файлу.bin>
    python scripts/read_bin.py <путь_к_файлу.bin> --hex    # только hex
    python scripts/read_bin.py <путь_к_файлу.bin> --raw   # только raw bytes
"""

import sys
import re
from pathlib import Path

from core.account.lock import AccountsLock
from core.services.gc.player_info_service import PlayerInfoService


def parse_filename(filename: str):
  """Извлекает EMsg ID из имени файла."""
  pattern = r"(\d+)_(in|out)_(\d+)_k_(.+)\.bin"
  match = re.match(pattern, filename)
  if match:
    return int(match.group(3))
  return None


def read_bin_file(filepath: Path):
  """Читает и выводит содержимое бинарного файла."""
  if not filepath.exists():
    print(f"❌ Файл не найден: {filepath}")
    return

  with open(filepath, "rb") as f:
    data = f.read()

  PlayerInfoService(AccountsLock()).process_message(data, "test")


def main():
  """Главная функция."""
  if len(sys.argv) < 2:
    print("Использование: python scripts/read_bin.py <файл.bin> [--hex|--raw]")
    sys.exit(1)

  filepath = Path(sys.argv[1])

  read_bin_file(filepath)


if __name__ == "__main__":
  main()
