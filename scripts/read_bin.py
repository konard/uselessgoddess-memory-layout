"""
Простая утилита для чтения бинарных файлов.

Использование:
    python scripts/read_bin.py <путь_к_файлу.bin>
    python scripts/read_bin.py <путь_к_файлу.bin> --hex    # только hex
    python scripts/read_bin.py <путь_к_файлу.bin> --raw   # только raw bytes
"""

import re
import sys
from pathlib import Path

# Add src to python path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from core.context import Context
from core.services.gc.gc_service import GCService


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

  msg_id = parse_filename(filepath.name)

  print(msg_id)
  GCService(Context()).process_message(data, msg_id, "test")


def main():
  """Главная функция."""
  if len(sys.argv) < 2:
    print("Использование: python scripts/read_bin.py <файл.bin> [--hex|--raw]")
    sys.exit(1)

  filepath = Path(sys.argv[1])

  read_bin_file(filepath)


if __name__ == "__main__":
  main()
