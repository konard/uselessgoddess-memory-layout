from typing import Optional

import asyncio
import os
import struct
import win32pipe
import win32file
import pywintypes
from dataclasses import dataclass
from core.logging import get_logger

from .gc_service import GCService

logger = get_logger("gc.server")

PIPE_NAME = r"\\.\pipe\SteamProtobufPipe"


def unicode_of(data: bytes) -> str:
  try:
    return data.decode("utf-8")
  except UnicodeDecodeError:
    return None


class PipeServer:
  def __init__(self, gc_service: GCService):
    self.gc_service = gc_service

  def _create_pipe_instance(self):
    return win32pipe.CreateNamedPipe(
      PIPE_NAME,
      win32pipe.PIPE_ACCESS_INBOUND,
      # forbid! PIPE_UNLIMITED_INSTANCES
      win32pipe.PIPE_TYPE_BYTE
      | win32pipe.PIPE_READMODE_BYTE
      | win32pipe.PIPE_WAIT,
      win32pipe.PIPE_UNLIMITED_INSTANCES,
      65536,  # Out buffer
      65536,  # In buffer
      0,
      None,
    )

  async def listen(self):
    loop = asyncio.get_running_loop()
    print(f"[{PIPE_NAME}] Сервер запущен. Жду клиентов...")

    while True:
      pipe_handle = self._create_pipe_instance()
      try:
        await loop.run_in_executor(
          None, win32pipe.ConnectNamedPipe, pipe_handle, None
        )
        asyncio.create_task(self.handle_client(pipe_handle))

      except Exception as e:
        logger.error(f"Error connection waing: {e}")
        win32file.CloseHandle(pipe_handle)

  def _read_exact_sync(self, pipe, size: int) -> bytes:
    if size == 0:
      return b""
    try:
      err, data = win32file.ReadFile(pipe, size)
      if len(data) < size:
        raise ConnectionAbortedError(f"Wanted {size}, got {len(data)}")
      return data
    except pywintypes.error as e:
      if e.winerror == 109:
        raise ConnectionResetError("Disconnected")
      raise e

  async def _read_sized_buf(
    self, loop, pipe, limit: int = 255
  ) -> Optional[bytes]:
    len_bytes = await loop.run_in_executor(None, self._read_exact_sync, pipe, 4)

    data_len = struct.unpack("<I", len_bytes)[0]
    if data_len > limit:
      logger.warn(f"crazy buffer length: {data_len}. Skip. Plz report")
      return None

    if data_len > 0:
      return await loop.run_in_executor(
        None, self._read_exact_sync, pipe, data_len
      )
    else:
      return None

  async def handle_client(self, pipe):
    loop = asyncio.get_running_loop()
    print("[PIPE] Ожидание данных...")

    try:
      while True:
        header_bytes = await loop.run_in_executor(
          None, self._read_exact_sync, pipe, 1 + 4
        )
        direction_id, msg_id = struct.unpack("<BI", header_bytes)

        if direction_id > 1:  # nor of 0,1
          logger.debug("skip invalid packet")
          break

        file_name = await self._read_sized_buf(loop, pipe)
        if file_name:
          file_name = unicode_of(file_name)
        if not file_name:
          logger.debug("skip invalid `file_name`")
          break

        client_name = await self._read_sized_buf(loop, pipe)
        if client_name:
          client_name = unicode_of(client_name)
        if not client_name:
          logger.debug("skip invalid `client_name`")
          break

        payload = await self._read_sized_buf(loop, pipe, limit=128 * 1024)
        if not payload:
          break

        direction_str = "in" if direction_id == 1 else "out"
        await self.process_packet(
          client_name, direction_str, msg_id, payload, file_name
        )

    except (ConnectionResetError, ConnectionAbortedError):
      pass
    except Exception as e:
      logger.error(f"[!] critical client error: {e}")
    finally:
      win32file.CloseHandle(pipe)

  async def process_packet(
    self,
    client_name: str,
    direction: str,
    msg_id: int,
    data: bytes,
    file_name: str,
  ):
    logger.trace(
      f"recv packet: id={msg_id} name={file_name}, login={client_name}, data=[{len(data)} bytes...]"
    )

    if data and len(data) > 0:
      os.makedirs(f"proto/{client_name}", exist_ok=True)
      filename = f"proto/{client_name}/{file_name.lower()}.bin"
      with open(filename, "wb") as f:
        f.write(data)

    if msg_id == 5453:
      self.gc_service.player_info_service.process_message(data, client_name)

    if msg_id == 800:
      self.gc_service.lobby_service.process_message(data)


async def start_gc_server(gc_service: GCService):
  server = PipeServer(gc_service)
  await server.listen()
