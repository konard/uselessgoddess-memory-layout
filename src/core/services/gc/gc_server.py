import asyncio
import struct
import win32pipe
import win32file
import pywintypes
from dataclasses import dataclass
from core.logging import get_logger

from .gc_service import GCService

logger = get_logger("gc.server")

PIPE_NAME = r"\\.\pipe\SteamProtobufPipe"


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

  async def handle_client(self, pipe):
    loop = asyncio.get_running_loop()
    print("[PIPE] Ожидание данных...")

    try:
      while True:
        name_len_bytes = await loop.run_in_executor(
          None, self._read_exact_sync, pipe, 4
        )
        name_len = struct.unpack("<I", name_len_bytes)[0]

        if name_len > 255:
          logger.warn(f"strange name length: {name_len}. Desync?")
          break

        client_name = None
        if name_len > 0:
          name_bytes = await loop.run_in_executor(
            None, self._read_exact_sync, pipe, name_len
          )
          try:
            client_name = name_bytes.decode("utf-8")
          except UnicodeDecodeError:
            pass

        header_bytes = await loop.run_in_executor(
          None, self._read_exact_sync, pipe, 9
        )
        direction_id, msg_id, data_size = struct.unpack("<BII", header_bytes)

        payload = b""
        if data_size > 0:
          if data_size > 100 * 1024 * 1024:
            logger.error(f"crazy packet size: {data_size} байт!")
            break

          payload = await loop.run_in_executor(
            None, self._read_exact_sync, pipe, data_size
          )

        direction_str = "in" if direction_id == 1 else "out"

        await self.process_packet(client_name, direction_str, msg_id, payload)

    except (ConnectionResetError, ConnectionAbortedError):
      pass
    except Exception as e:
      logger.error(f"[!] critical client error: {e}")
    finally:
      win32file.CloseHandle(pipe)

  async def process_packet(
    self, client_name: str, direction: str, msg_id: int, data: bytes
  ):
    logger.trace(f"({msg_id}) process packet with {len(data)} bytes payload")

    if msg_id == 5453:
      self.gc_service.player_info_service.process_message(data, client_name)

    if msg_id == 800:
      self.gc_service.lobby_service.process_message(data)


async def start_gc_server(gc_service: GCService):
  server = PipeServer(gc_service)
  await server.listen()
