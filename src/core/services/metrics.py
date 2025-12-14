import asyncio
import time
import requests
import gzip
import base64
import json
import atexit
from typing import Any, Dict

from core.logging import get_logger
from core.services.license import LicenseService

logger = get_logger("metrics")

METRICS_URL = "http://188.127.224.201:3000/api/metrics"


class MetricsService:
  def __init__(self, lic: LicenseService):
    self.lic = lic
    self.uptime = time.time()
    atexit.register(self._send_shutdown_metric)

  def _send_shutdown_metric(self):
    try:
      payload = {"uptime": time.time() - self.uptime}
      data = {
        "type": "shutdown",
        "license_key": self.lic.license_key,
        "machine_id": self.lic.machine_id,
        "session_id": self.lic.session_id,
        "data": payload,
      }

      compressed = gzip.compress(json.dumps(data).encode("utf-8"))
      encoded = base64.b64encode(compressed).decode("utf-8")
      requests.post(METRICS_URL, json={"stats": encoded}, timeout=5)
    except Exception:
      pass

  async def send(self, type: str, payload: Dict[str, Any]):
    data = {
      "type": type,
      "license_key": self.lic.license_key,
      "machine_id": self.lic.machine_id,
      "session_id": self.lic.session_id,
      "data": payload,
    }
    await self._send_request(data)

  async def _send_request(self, payload: Dict[str, Any]):
    def _request():
      try:
        compressed = gzip.compress(json.dumps(payload).encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("utf-8")
        requests.post(METRICS_URL, json={"stats": encoded}, timeout=5)
      except Exception:
        pass

    try:
      loop = asyncio.get_running_loop()
      await loop.run_in_executor(None, _request)
    except RuntimeError:
      pass
