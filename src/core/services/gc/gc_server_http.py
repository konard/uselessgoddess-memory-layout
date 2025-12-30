import os
import traceback

import uvicorn
from fastapi import FastAPI, Request, Response
from starlette.requests import ClientDisconnect

from constants import IS_DEV_MODE
from core import utils
from core.logging import get_logger

from .gc_service import GCService

logger = get_logger("gc.server.http")
PORT = 13337


def save_sync(file: str, data: bytes):
  with open(file, "wb") as f:
    f.write(data)


async def start_gc_server(gc_service: GCService):
  app = FastAPI()

  @app.post("/log")
  async def receive_message(request: Request):
    try:
      msg_id_str = request.headers.get("X-MsgID", "0")
      msg_id = int(msg_id_str) if msg_id_str.isdigit() else 0
      filename = request.headers.get("X-FileName", "?")
      client_name = request.headers.get("X-ClientName", "")

      data = await request.body()

      # logger.trace(
      #   f"<recv> gc message: [{msg_id}]; {client_name} {filename} ({len(data)} bytes)"
      # )

      if IS_DEV_MODE and data and len(data) > 0:
        try:
          os.makedirs(f"proto/{client_name}", exist_ok=True)
          safe_filename = os.path.basename(filename)
          if not safe_filename:
            safe_filename = "unknown.bin"
          save_path = f"proto/{client_name}/{safe_filename.lower()}.bin"
          await utils.run_blocking(save_sync, save_path, data)
        except Exception as e:
          logger.error(f"Failed to save proto dump: {e}")

      gc_service.process_message(data, msg_id, client_name)

      return Response(status_code=200)

    except ClientDisconnect:
      pass
    except Exception as e:
      logger.error(f"Error handling request: {e}")
      logger.error(traceback.format_exc())
      return Response(status_code=500)

  config = uvicorn.Config(
    app=app,
    host="127.0.0.1",
    port=PORT,
    log_level="critical",
    access_log=False,
    loop="asyncio",
  )
  server = uvicorn.Server(config)

  logger.info(f"Starting NetHook2 HTTP Receiver on 127.0.0.1:{PORT}...")
  await server.serve()
