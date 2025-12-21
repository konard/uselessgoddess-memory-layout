import traceback
from typing import Optional

import asyncio
import os
import struct
import win32pipe
import win32file
import pywintypes
from dataclasses import dataclass
from core.logging import get_logger

from constants import IS_DEV_MODE

from .gc_service import GCService

logger = get_logger("gc.server")

PIPE_NAME = r"\\.\pipe\SteamProtobufPipe"
BUFFER_SIZE = 65536


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
      win32pipe.PIPE_TYPE_MESSAGE
      | win32pipe.PIPE_READMODE_MESSAGE
      | win32pipe.PIPE_WAIT,
      255,  # Max instances
      BUFFER_SIZE,  # Out buffer
      BUFFER_SIZE,  # In buffer
      0,  # Timeout
      None,  # Security attributes
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
        try:
          win32file.CloseHandle(pipe_handle)
        except Exception:
          pass

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
      return b""

  async def handle_client(self, pipe):
    loop = asyncio.get_running_loop()
    logger.debug("[PIPE] Ожидание данных...")

    try:
      while True:
        header_bytes = await loop.run_in_executor(
          None, self._read_exact_sync, pipe, 1 + 4
        )
        direction_id, msg_id = struct.unpack("<BI", header_bytes)

        if direction_id > 1:  # nor of 0,1
          logger.debug("skip invalid packet")
          break

        file_name_bytes = await self._read_sized_buf(loop, pipe)
        if file_name_bytes is None:
          logger.debug("skip invalid `file_name` length")
          break

        file_name = unicode_of(file_name_bytes)
        if file_name is None:
          logger.debug("skip invalid `file_name` encoding")
          break

        client_name_bytes = await self._read_sized_buf(loop, pipe)
        if client_name_bytes is None:
          logger.debug("skip invalid `client_name` length")
          break

        client_name = unicode_of(client_name_bytes)
        if client_name is None:
          logger.debug("skip invalid `client_name` encoding")
          break

        payload = await self._read_sized_buf(loop, pipe, limit=128 * 1024)
        if payload is None:
          logger.debug("skip invalid `payload` length")
          break

        direction_str = "in" if direction_id == 1 else "out"
        await self.process_packet(
          client_name, direction_str, msg_id, payload, file_name
        )

    except (ConnectionResetError, ConnectionAbortedError):
      pass
    except Exception as e:
      logger.error(f"[!] critical client error: {e}")
      print(traceback.format_exc())
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
    # logger.trace(
    #   f"recv packet: id={msg_id} name={file_name}, login={client_name}, data=[{len(data)} bytes...]"
    # )

    if IS_DEV_MODE and data and len(data) > 0:
      os.makedirs(f"proto/{client_name}", exist_ok=True)
      filename = f"proto/{client_name}/{file_name.lower()}.bin"
      with open(filename, "wb") as f:
        f.write(data)

    self.gc_service.process_message(data, msg_id, client_name)


async def start_gc_server(gc_service: GCService):
  server = PipeServer(gc_service)
  await server.listen()
