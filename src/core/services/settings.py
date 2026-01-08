import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, ValidationError, field_validator

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
      with open(path) as f:
        data = json.load(f)
        logger.info(f"{label} loaded successfully.")
        return ty(**data)
  except ValidationError as e:
    from PyQt6.QtWidgets import QMessageBox

    error_msg = "\n".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
    QMessageBox.critical(None, "Config error", f"Check settings.json:\n{error_msg}")

  except Exception as e:
    logger.error(f"Failed to load '{path}': {e}.")

  logger.debug(f"Using default {label}.")
  return ty()


def _save_settings(path, settings, label="settings"):
  try:
    data = settings.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
    logger.debug(f"{label} saved to '{path}'.")
  except Exception as e:
    logger.error(f"Failed to save '{path}': {e}")


class Settings(BaseModel):
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


class InferenceDevice(str, Enum):
  CPU = "cpu"
  GPU = "gpu"


class MatchSettings(BaseModel):
  fast_paths: bool = Field(False, description="Enable fast paths")
  no_plant: bool = Field(False, description="Disable plant behaviour")
  no_buy: bool = Field(False, description="Disable buy menu behaviour, prefer autobuy")


class AdvancedSettings(BaseModel):
  inference_device: InferenceDevice = Field(
    InferenceDevice.CPU, description="Execution provider"
  )
  inference_threads: int = Field(0, ge=0, le=32, description="Intra-op num threads")
  debug_render: bool = Field(False, description="Enable visual debug in production")

  match: MatchSettings = Field(default_factory=MatchSettings)


class UserSettings(Settings):
  license_key: str = Field("")
  trade_url: str = Field("", description="Main trade url link")
  steam_path: str = Field("", description="Path to steam exe")
  cs_path: str = Field("", description="Path to CS2 folder")
  win_w: int = Field(360, ge=360)
  win_h: int = Field(270, ge=270)

  experimental_launch: bool = Field(True)

  telegram_token: str | None = Field(None)
  telegram_whitelist: list[str] = Field(
    default_factory=list, description="Your and your friends' tg ids"
  )

  collect_available_steam_games_on_login: bool = Field(False)

  extension_ids: list[str] = Field(
    default_factory=lambda: ["cmeakgjggjdlcpncigglobpjbkabhmjl"],
    description="Chrome required extensions (SIH, etc.)",
  )

  # farm settings
  match_mode: MatchMode = Field(MatchMode.TIE)
  times_to_shuffle: int = Field(3)
  times_to_brute_force: int = Field(3)
  farm_until: str | None = Field(None)
  overfarm: int | None = Field(None)

  advanced: AdvancedSettings = Field(default_factory=AdvancedSettings)

  def path_of(self, settings: "SettingsService"):
    return settings.user_file

  @staticmethod
  def load(path) -> "UserSettings":
    return _load_settings(path, UserSettings, "user settings")

  def save(self, path):
    _save_settings(path, self, "user settings")


class SystemState(Settings):
  shuffle_lobbies: bool = Field(True)
  collect_drop: bool = Field(False)
  farm_on_launch: bool = Field(True)
  farm_mode: FarmMode = Field(FarmMode.TWO_BY_TWO)

  def path_of(self, settings: "SettingsService"):
    return settings.system_file

  @staticmethod
  def load(path) -> "SystemState":
    return _load_settings(path, SystemState, "system state")

  def save(self, path):
    _save_settings(path, self, "system state")


class SettingsService:
  def __init__(self, user_file="settings.json", system_file="data/settings.lock"):
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
