import asyncio
import contextlib
import hashlib
import random
import subprocess
import uuid
from dataclasses import dataclass
from enum import Enum

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from constants import CHECK_LICENSE
from core.logging import get_logger
from core.services.settings import UserSettings

logger = get_logger("sv.license")

# TODO: эво кодим сервачок
# TODO: obfuscate pls
# API_URL = "http://localhost:3000/api/heartbeat"
API_URL = "http://188.127.224.201:3000/api/heartbeat"
CLIENT_SECRET = "7f8a9d0e1b2c3d4e5f6g7h8i9j0k1l2m"


def generate_magic(session_id: str, secret: str) -> int:
  combined = f"{session_id}{secret}"
  data = combined.encode("utf-8")

  FNV_OFFSET_BASIS = 0xCBF29CE484222325
  FNV_PRIME = 0x100000001B3

  hash_val = FNV_OFFSET_BASIS

  for byte in data:
    hash_val ^= byte
    hash_val *= FNV_PRIME
    hash_val &= 0xFFFFFFFFFFFFFFFF

  if hash_val >= 2**63:
    hash_val -= 2**64

  return hash_val


class LicenseKind(Enum):
  VALID = "valid"
  PAUSED_NETWORK = "paused_network"
  PAUSED_LIMIT = "paused_limit"
  INVALID = "invalid"
  BANNED = "banned"


@dataclass
class HeartbeatResponse:
  success: bool
  status_code: int
  magic_token: int = 0  # Anti-Tamper
  message: str = ""


class LicenseService(QObject):
  state_changed = pyqtSignal(LicenseKind)
  fatal_error = pyqtSignal(str)

  def __init__(self, settings: UserSettings):
    super().__init__()
    self.settings = settings

    self.license_key = self.settings.license_key
    self.machine_id = self._get_persistent_hwid()
    self.session_id = str(uuid.uuid4())

    self._running = False
    self._fail_count = 0
    self._state = LicenseKind.INVALID

    # time.sleep(1.0 / self.magic_token)
    self.magic_token = 1

  def _get_persistent_hwid(self) -> str:
    try:
      cmd = "wmic csproduct get uuid"
      output = subprocess.check_output(cmd, shell=True).decode()
      raw_uuid = output.split("\n")[1].strip()
      if not raw_uuid:
        raise ValueError("Empty UUID")

      return hashlib.sha256(raw_uuid.encode()).hexdigest()
    except Exception as e:
      logger.error(f"Failed to get HWID: {e}. Fallback to node.")
      return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()

  async def start(self):
    if self._running:
      return
    self._running = True
    logger.debug(f"license Service started. session: {self.session_id}")

    # TODO: use decoupled constant to check license even in dev mode
    if CHECK_LICENSE:
      await self._heartbeat_loop()

  async def stop(self):
    self._running = False

  async def _heartbeat_loop(self):
    loop = asyncio.get_running_loop()

    while self._running:
      try:
        response = await loop.run_in_executor(None, self._send_request)

        await self._handle_response(response)

      except Exception as e:
        logger.error(f"Heartbeat loop critical error: {e}")
        self._handle_network_failure()

      sleep_time = 30 + random.uniform(1, 5)
      await asyncio.sleep(sleep_time)

  def _send_request(self) -> HeartbeatResponse:
    payload = {
      "key": self.license_key,
      "machine_id": self.machine_id,
      "session_id": self.session_id,
    }

    try:
      r = requests.post(API_URL, json=payload, timeout=10)

      data = {}
      with contextlib.suppress(Exception):
        data = r.json()

      token = data.get("magic_token", 1)
      if token is None:
        token = 0

      return HeartbeatResponse(
        success=r.status_code == 200,
        status_code=r.status_code,
        magic_token=int(token),
        message=data.get("message", "Unknown error"),
      )
    except requests.RequestException:
      return HeartbeatResponse(success=False, status_code=0)

  async def _handle_response(self, resp: HeartbeatResponse):
    if resp.success:
      expected = generate_magic(self.session_id, CLIENT_SECRET)

      self._fail_count = 0
      if expected == resp.magic_token and self._state != LicenseKind.VALID:
        self._set_state(LicenseKind.VALID)
        logger.info("License validated. Resuming work.")
      return

    if resp.status_code == 0 or resp.status_code >= 500:
      self._handle_network_failure()
      return

    self._fail_count = 0

    if resp.status_code == 409:  # Conflict (Limit reached)
      if self._state != LicenseKind.PAUSED_LIMIT:
        logger.warn("Session limit reached. Pausing work.")
        self._set_state(LicenseKind.PAUSED_LIMIT)
      return

    if resp.status_code in [401, 403]:  # Invalid or Banned
      logger.critical(f"License fatal error: {resp.message}")
      self._set_state(LicenseKind.BANNED)
      # self._running = False -- DO NOT STOP WHEN BANNED
      self.fatal_error.emit(f"License Error ({resp.status_code}):\n{resp.message}")
      return

  def _handle_network_failure(self):
    self._fail_count += 1
    logger.warn(f"Network error. Attempt {self._fail_count}/3")

    if self._fail_count >= 3:
      if self._state != LicenseKind.PAUSED_NETWORK:
        logger.error("Network instability detected. Pausing work.")
        self._set_state(LicenseKind.PAUSED_NETWORK)
    else:
      # Grace Period
      pass

  def _set_state(self, new_state: LicenseKind):
    self._state = new_state
    self.state_changed.emit(new_state)

  def state(self) -> LicenseKind:
    return self._state

  def is_working(self) -> bool:
    return self._state == LicenseKind.VALID or (
      self._state == LicenseKind.PAUSED_NETWORK and self._fail_count < 1
    )

  def update_key(self, new_key: str):
    self.license_key = new_key
    self.settings.license_key = new_key
