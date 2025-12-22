import http.server
import socketserver
import sys
import os
import asyncio
import traceback
from functools import partial
from core.logging import get_logger
from constants import IS_DEV_MODE
from .gc_service import GCService

logger = get_logger("gc.server.http")
PORT = 13337


class NetHookHandler(http.server.BaseHTTPRequestHandler):
  def do_POST(self):
    try:
      length = int(self.headers.get("Content-Length", 0))

      # Read metadata from headers
      direction = self.headers.get("X-Direction", "UNK")
      msg_id_str = self.headers.get("X-MsgID", "0")
      msg_id = int(msg_id_str) if msg_id_str.isdigit() else 0
      filename = self.headers.get("X-FileName", "?")
      client_name = self.headers.get("X-ClientName", "")

      # Read body (binary data)
      data = self.rfile.read(length)

      # Log info
      client_info = f" [{client_name}]" if client_name else ""
      logger.debug(
        f"[{direction}]{client_info} MsgID: {msg_id:<6} Size: {length:<6} File: {filename}"
      )

      # Dev mode saving
      if IS_DEV_MODE and data and len(data) > 0:
        try:
          os.makedirs(f"proto/{client_name}", exist_ok=True)
          # Safe filename handling
          safe_filename = os.path.basename(filename)
          if not safe_filename:
            safe_filename = "unknown.bin"
          save_path = f"proto/{client_name}/{safe_filename.lower()}.bin"
          with open(save_path, "wb") as f:
            f.write(data)
        except Exception as e:
          logger.error(f"Failed to save proto dump: {e}")

      # Process message
      if self.server.gc_service:
        # direction logic: "in" if direction == "1" else "out" (based on previous code)
        # But here direction is a string "IN" or "OUT" or "UNK" from headers?
        # User's snippet prints direction directly.
        # Old code: direction_id=1 -> "in", else "out".
        # We'll just pass data to process_message.
        # Note: process_message signature in old code: (data, msg_id, client_name)
        self.server.gc_service.process_message(data, msg_id, client_name)

      self.send_response(200)
      self.end_headers()

    except Exception as e:
      logger.error(f"Error handling request: {e}")
      logger.error(traceback.format_exc())
      self.send_response(500)
      self.end_headers()

  def log_message(self, format, *args):
    # Disable default request logging
    pass


class GCHTTPServer(socketserver.TCPServer):
  allow_reuse_address = True

  def __init__(self, server_address, RequestHandlerClass, gc_service):
    self.gc_service = gc_service
    super().__init__(server_address, RequestHandlerClass)


def run_server_blocking(gc_service: GCService):
  logger.info(f"Starting NetHook2 HTTP Receiver on 127.0.0.1:{PORT}...")
  with GCHTTPServer(("127.0.0.1", PORT), NetHookHandler, gc_service) as httpd:
    try:
      httpd.serve_forever()
    except Exception as e:
      logger.error(f"Server error: {e}")


async def start_gc_server(gc_service: GCService):
  loop = asyncio.get_running_loop()
  # Run blocking server in executor to avoid blocking the async loop
  await loop.run_in_executor(None, run_server_blocking, gc_service)
