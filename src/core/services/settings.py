import json
import os
from enum import Enum
from typing import Callable, Optional, List
from dataclasses import asdict, dataclass, field
from core.logging import get_logger
from core.utils import name_of

logger = get_logger("settings")

SETTINGS_FILE = "settings.json"


class FarmMode(str, Enum):
  TWO_BY_TWO = "2x2"
  FIVE_BY_FIVE = "5x5"


class MatchMode(str, Enum):
  TIE = "tie"
  RANDOM = "random"


def _load_settings(path, ty, label="settings"):
  try:
    if os.path.exists(path):
      with open(path, "r") as f:
        data = json.load(f)
        logger.info(f"{label} loaded successfully.")
        return ty(**data)
  except Exception as e:
    logger.error(f"Failed to load '{path}': {e}.")
    pass
  logger.debug(f"Using default {label}.")
  return ty()


def _save_settings(path, settings, label="settings"):
  try:
    data = asdict(settings)
    # Преобразуем enum в строку для JSON сериализации
    for key, value in data.items():
      if isinstance(value, Enum):
        data[key] = value.value
    with open(path, "w") as f:
      json.dump(data, f, indent=2)
    logger.debug(f"{label} saved to '{path}'.")
  except Exception as e:
    logger.error(f"Failed to save '{path}': {e}")


class Settings:
  def path_of(self, settings: "SettingsService"):
    pass

  def state_updater(
    self, settings: "SettingsService", key: str
  ) -> Callable[[bool], None]:
    def updater(value: bool):
      if hasattr(self, key):
        setattr(self, key, value)
        logger.trace(f"{name_of(self)} '{key}' updated to {value} -> saving...")
        self.save(self.path_of(settings))
      else:
        logger.warn(f"Settings has no attribute '{key}' to update.")

    return updater


@dataclass
class UserSettings(Settings):
  license_key: str = ""
  trade_url: str = ""
  steam_path: str = ""
  cs_path: str = ""
  win_w: int = 360
  win_h: int = 270

  experimental_launch: bool = True

  telegram_token: Optional[str] = None
  telegram_whitelist: List[str] = field(default_factory=list)

  collect_available_steam_games_on_login: bool = False

  extension_ids: List[str] = field(
    default_factory=lambda: ["cmeakgjggjdlcpncigglobpjbkabhmjl"]
  )

  # farm settings
  match_mode: MatchMode = MatchMode.TIE
  times_to_shuffle: int = 3
  times_to_brute_force: int = 3
  farm_until: Optional[str] = None
  overfarm: Optional[int] = None

  def path_of(self, settings: "SettingsService"):
    return settings.user_file

  @staticmethod
  def load(path) -> "UserSettings":
    return _load_settings(path, UserSettings, "user settings")

  def save(self, path):
    _save_settings(path, self, "user settings")


@dataclass
class SystemState(Settings):
  shuffle_lobbies: bool = True
  collect_drop: bool = False
  farm_on_launch: bool = True
  farm_mode: FarmMode = FarmMode.TWO_BY_TWO

  def path_of(self, settings: "SettingsService"):
    return settings.system_file

  @staticmethod
  def load(path) -> "SystemState":
    return _load_settings(path, SystemState, "system state")

  def save(self, path):
    _save_settings(path, self, "system state")


class SettingsService:
  def __init__(
    self, user_file="settings.json", system_file="data/settings.lock"
  ):
    self.user_file = user_file
    self.system_file = system_file
    self.reload()

  def reload(self):
    self.user = UserSettings.load(self.user_file)
    logger.debug(f"User settings loaded: {self.user}")
    self.system = SystemState.load(self.system_file)
    logger.debug(f"System state loaded: {self.system}")

  def set_user(self, user: UserSettings):
    self.user = user
    self.save(self.user)

  def set_system(self, user: UserSettings):
    self.system = user
    self.save(self.system)

  def save(self, settings):
    settings.save(self.user_file)

  @property
  def u(self):
    return self.user

  @property
  def s(self):
    return self.system
