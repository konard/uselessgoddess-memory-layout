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

from steam._gc import AppID
from steam.protobufs import GCMessage, GCProtobufMessage, ProtobufMessage

from steam.protobufs import ProtobufMessage, Message
from steam._const import READ_U32, IS_PROTO, CLEAR_PROTO_BIT

import steam.ext.csgo.protobufs


def decode_bytes(data: bytes):
  """
  Декодирует бинарные данные Steam протокола в объект сообщения.

  Args:
      data: Байты сообщения (с EMsg в первых 4 байтах)

  Returns:
      ProtobufMessage или Message объект
  """
  # Читаем первые 4 байта - это EMsg (тип сообщения)
  emsg_value = READ_U32(data)

  # Проверяем флаг protobuf (бит 0x80000000)
  if IS_PROTO(emsg_value):
    # Это protobuf сообщение
    msg = ProtobufMessage().parse(data[4:], CLEAR_PROTO_BIT(emsg_value))
  else:
    # Это структурированное сообщение
    msg = Message().parse(data[4:], emsg_value)

  return msg


def decode_gc_bytes(data: bytes, app_id: int = 730):
  """
  Декодирует GC (Game Coordinator) сообщение.

  Args:
      data: Байты сообщения (с EMsg в первых 4 байтах)
      app_id: ID приложения (730 для CS:GO, 440 для TF2, и т.д.)
  """
  emsg_value = READ_U32(data)

  if IS_PROTO(emsg_value):
    msg = GCProtobufMessage().parse(
      data[4:], CLEAR_PROTO_BIT(emsg_value), AppID(app_id)
    )
  else:
    msg = GCMessage().parse(data[4:], emsg_value, AppID(app_id))

  return msg


def parse_filename(filename: str):
  """Извлекает EMsg ID из имени файла."""
  pattern = r"(\d+)_(in|out)_(\d+)_k_(.+)\.bin"
  match = re.match(pattern, filename)
  if match:
    return int(match.group(3))
  return None


def read_bin_file(
  filepath: Path, hex_only: bool = False, raw_only: bool = False
):
  """Читает и выводит содержимое бинарного файла."""
  if not filepath.exists():
    print(f"❌ Файл не найден: {filepath}")
    return

  with open(filepath, "rb") as f:
    data = f.read()

  print("=" * 80)
  print(f"📁 Файл: {filepath.name}")
  print(f"📏 Размер: {len(data)} байт")
  print("=" * 80)
  print()

  decoded_message = decode_bytes(data)
  if hasattr(decoded_message, "payload"):
    payload = decode_gc_bytes(decoded_message.payload)
    print(payload)


def main():
  """Главная функция."""
  if len(sys.argv) < 2:
    print("Использование: python scripts/read_bin.py <файл.bin> [--hex|--raw]")
    sys.exit(1)

  filepath = Path(sys.argv[1])
  hex_only = "--hex" in sys.argv
  raw_only = "--raw" in sys.argv

  read_bin_file(filepath, hex_only, raw_only)


if __name__ == "__main__":
  main()
