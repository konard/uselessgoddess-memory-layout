#!/usr/bin/env python3
"""
Простой FastAPI сервер для приёма сообщений от NetHook2
"""

from dataclasses import dataclass
import uvicorn
from fastapi import FastAPI, Depends

from .gc_service import GCService


@dataclass
class SteamMessage:
  timestamp: int
  direction: str
  msgId: int
  msgName: str
  size: int
  Name: str
  fileName: str
  data: str


app = FastAPI()

gc_service_instance: GCService = None


def get_gc_service() -> GCService:
  if gc_service_instance is None:
    raise RuntimeError(
      "GCService не инициализирован! Вызовите main() с экземпляром GCService"
    )
  return gc_service_instance


@app.post("/steam-message")
async def receive_steam_message(
  message: SteamMessage, gc_service: GCService = Depends(get_gc_service)
):
  """Приём Steam сообщений от NetHook2"""
  from datetime import datetime
  import base64

  timestamp_str = datetime.fromtimestamp(message.timestamp).strftime(
    "%Y-%m-%d %H:%M:%S"
  )

  binary_data = None

  print("=" * 80)
  print(f"Timestamp: {timestamp_str} ({message.timestamp})")
  print(f"Direction: {message.direction.upper()}")
  print(f"Message ID: {message.msgId}")
  print(f"Message Name: {message.msgName}")
  print(f"Size: {message.size} bytes")
  print(f"Client Name: {message.Name}")
  print(f"File Name: {message.fileName}")
  print("=" * 80)

  if message.msgId == 5453:
    gc_service.player_info_service.process_message(binary_data, message.Name)

  # # Сохраняем бинарные данные с оригинальным именем файла
  # if binary_data and len(binary_data) > 0:
  #   filename = f"{message.fileName}.bin"
  #   with open(filename, "wb") as f:
  #     f.write(binary_data)
  #   print(f"💾 Saved binary data to: {filename}")
  #   print()

  # gc_service.matcher.set_match_id(message.Name, 1123)

  return {
    "status": "ok",
    "received_bytes": len(binary_data) if binary_data else 0,
  }


async def start_gc_server(gc_service: GCService):
  """Запуск FastAPI сервера с переданным экземпляром GCService"""
  global gc_service_instance
  gc_service_instance = gc_service

  config = uvicorn.Config(
    app, host="127.0.0.1", port=8631, log_level="error", access_log=False
  )
  server = uvicorn.Server(config)
  await server.serve()
