import json
import os
from dataclasses import asdict, dataclass
from core.logging import get_logger
from core.utils import name_of

logger = get_logger("settings")

SETTINGS_FILE = "settings.json"


@dataclass
class UserSettings:
  trade_url: str = ""
  steam_path: str = ""
  cs_path: str = ""
  win_w: int = 360
  win_h: int = 270


@dataclass
class SystemState:
  shuffle_lobbies: bool = True
  auto_collect_drop: bool = False
  start_farm_on_launch: bool = True


class SettingsService:
  def __init__(
    self, user_file="settings.json", system_file="data/settings.lock"
  ):
    self.user_file = user_file
    self.system_file = system_file

    self.user = self._load_settings(self.user_file, UserSettings, "settings")
    logger.trace(f"User settings loaded: {self.user}")
    self.system = self._load_settings(self.system_file, SystemState, "system state")
    logger.trace(f"System state loaded: {self.system}")

  def _load_settings(self, path, ty, name):
    try:
      if os.path.exists(path):
        with open(path, "r") as f:
          data = json.load(f)
          logger.info(f"{name} loaded successfully.")
          return ty(**data)
    except Exception as e:
      logger.error(f"Failed to load '{path}': {e}.")
      pass
    logger.debug(f"Using default {name}.")
    return ty()

  def save_system_state(self):
    try:
      with open(self.system_file, "w") as f:
        json.dump(asdict(self.system), f, indent=4)
      logger.info(f"System state saved to '{self.system_file}'.")
    except Exception as e:
      logger.error(f"Failed to save system state to '{self.system_file}': {e}")
