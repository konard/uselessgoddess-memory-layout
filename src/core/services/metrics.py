import asyncio
import requests
from typing import Any, Dict

from core.logging import get_logger

logger = get_logger("metrics")

METRICS_URL = "http://188.127.224.201:3000/api/metrics"


class MetricsService:
  def __init__(self):
    pass

  async def send(self, type: str, payload: Dict[str, Any]):
    data = payload.copy()
    data["type"] = type
    await self._send_request(data)

  async def _send_request(self, payload: Dict[str, Any]):
    def _request():
      try:
        requests.post(METRICS_URL, json=payload, timeout=5)
      except Exception:
        pass

    try:
      loop = asyncio.get_running_loop()
      await loop.run_in_executor(None, _request)
    except RuntimeError:
      pass
