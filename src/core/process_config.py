"""
ConfigService - применение конфигураций CS2
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import stat
import winreg
from pathlib import Path
from typing import TYPE_CHECKING

from core.logging import get_logger

if TYPE_CHECKING:
  from core.context import Context
from utils.map_steam64_to_steam3 import map_steam64_to_steam3

logger = get_logger("yacs.config")

DATA_DIR = Path("data")
YACS_CFG_SRC = DATA_DIR / "yacs.cfg"
GSI_CFG_SRC = DATA_DIR / "gamestate_integration.cfg"
VIDEO_TEMPLATE_PATH = DATA_DIR / "video.txt"
CS2_MACHINE_CONVARS_SRC = DATA_DIR / "cs2_machine_convars.vcfg"

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
STEAM_STORE_BLOCK_LINE = "0.0.0.0 store.steampowered.com"

_cleanup_context: Context | None = None


def _cleanup_steam_store_block():
  if _cleanup_context is None:
    return
  try:
    config_service = ConfigService(_cleanup_context)
    config_service.unblock_steam_store()
  except Exception:
    pass


atexit.register(_cleanup_steam_store_block)


class ConfigService:
  def __init__(self, ctx: Context) -> None:
    self.ctx = ctx
    global _cleanup_context
    _cleanup_context = ctx

  def ensure_cs_cfgs(self) -> None:
    csgo_path = Path(self.ctx.s.u.cs_path)
    cfg_dir = csgo_path / "game" / "csgo" / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    self._copy_config_files(cfg_dir)

  def apply_video_config(self, steam_id: str) -> None:
    if not steam_id:
      logger.warn("Пустой steam_id — пропуск apply_video_config")
      return

    userdata_dir = self._find_userdata_dir()
    target_cfg_dirs = self._ensure_cfg_directories(
      userdata_dir, map_steam64_to_steam3(steam_id)
    )
    if not target_cfg_dirs:
      return

    template_kv = self._load_video_template()
    if template_kv is None:
      return

    # ### Получаем ID видеокарты без PowerShell (через реестр)
    system_gpu_kv = self._get_system_gpu_ids()

    for target_cfg_dir in target_cfg_dirs:
      self._copy_file_if_exists(
        CS2_MACHINE_CONVARS_SRC,
        target_cfg_dir / "cs2_machine_convars.vcfg",
        "cs2_machine_convars.vcfg",
      )
      current_kv = self._load_current_video_config(target_cfg_dir)
      merged_kv = self._merge_video_configs(current_kv, template_kv)

      # ### Внедряем полученные ID
      if system_gpu_kv:
        merged_kv.update(system_gpu_kv)
        logger.trace(f"В конфиг внедрены GPU ID (Reg): {system_gpu_kv}")

      self._save_video_config(target_cfg_dir, merged_kv, steam_id)

  def _get_system_gpu_ids(self) -> dict[str, str]:
    """
    Получает VendorID и DeviceID из реестра Windows.
    Ищет в классе устройств Display Adapters GUID: {4d36e968-e325-11ce-bfc1-08002be10318}
    """
    display_class_guid = "{4d36e968-e325-11ce-bfc1-08002be10318}"
    base_key_path = rf"SYSTEM\CurrentControlSet\Control\Class\{display_class_guid}"

    try:
      with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key_path) as key:
        for i in range(10):
          try:
            subkey_name = winreg.EnumKey(key, i)
            with winreg.OpenKey(key, subkey_name) as subkey:
              try:
                hw_id, _ = winreg.QueryValueEx(subkey, "MatchingDeviceId")

                match = re.search(
                  r"VEN_([0-9A-Fa-f]+)&DEV_([0-9A-Fa-f]+)", hw_id, re.IGNORECASE
                )

                if match:
                  ven_hex = match.group(1)
                  dev_hex = match.group(2)

                  # Конвертируем HEX -> DEC
                  return {
                    "VendorID": str(int(ven_hex, 16)),
                    "DeviceID": str(int(dev_hex, 16)),
                  }
              except FileNotFoundError:
                continue
          except OSError:
            break  # Подпапки закончились
    except Exception as e:
      logger.error(f"Ошибка при чтении реестра GPU: {e}")

    return {}

  def delete_video_config(self, steam_id: str) -> None:
    try:
      userdata_dir = self._find_userdata_dir()
      steam3_id = map_steam64_to_steam3(steam_id)
      account_dir = userdata_dir / str(steam3_id)
      if account_dir.exists():

        def on_rm_error(func, path, exc_info):
          try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
          except Exception:
            pass

        try:
          shutil.rmtree(account_dir, onerror=on_rm_error)
          logger.debug(f"Удалена папка аккаунта: {account_dir}")
        except Exception as e:
          logger.warning(f"Не удалось удалить папку {account_dir}: {e}")
    except Exception:
      logger.warning(f"Не удалось удалить папку {account_dir}")

  def _copy_config_files(self, cfg_dir: Path) -> None:
    try:
      self._copy_file_if_exists(YACS_CFG_SRC, cfg_dir / "yacs.cfg", "yacs.cfg")
      self._copy_file_if_exists(
        GSI_CFG_SRC,
        cfg_dir / "gamestate_integration_sex.cfg",
        "gamestate_integration.cfg",
      )
    except Exception:
      logger.exception("Не удалось скопировать конфигурационные файлы")

  def _copy_file_if_exists(self, src: Path, dst: Path, file_name: str) -> None:
    if not src.exists():
      return
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    logger.debug(f"Обновлен `{file_name}` -> `{dst}`")

  def _find_userdata_dir(self) -> Path:
    steam_path = self.ctx.s.u.steam_path
    steam_dir = Path(steam_path).parent
    candidates = [steam_dir / "userdata", steam_dir.parent / "userdata"]
    for candidate in candidates:
      if candidate.exists() or (not candidate.exists() and candidate.parent.exists()):
        return candidate
    return steam_dir / "userdata"

  def _ensure_cfg_directories(self, userdata_dir: Path, steam_id: str) -> list[Path]:
    base_dir = userdata_dir / str(steam_id) / "730"
    targets = [base_dir / "local" / "cfg"]
    created = []
    for target in targets:
      try:
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)
      except Exception:
        logger.exception(f"Не удалось создать каталог: {target}")
    return created

  def _load_video_template(self) -> dict[str, str] | None:
    if not VIDEO_TEMPLATE_PATH.exists():
      logger.warn(f"Шаблон video.txt не найден: {VIDEO_TEMPLATE_PATH}")
      return None
    try:
      template_text = VIDEO_TEMPLATE_PATH.read_text(encoding="utf-8")
      return _parse_video_kv(template_text)
    except Exception:
      logger.exception(f"Не удалось прочитать шаблон video.txt: {VIDEO_TEMPLATE_PATH}")
      return None

  def _load_current_video_config(self, cfg_dir: Path) -> dict[str, str]:
    target_video = cfg_dir / "cs2_video.txt"
    if not target_video.exists():
      target_video = cfg_dir / "video.txt"
      if not target_video.exists():
        return {}
    try:
      current_text = target_video.read_text(encoding="utf-8", errors="ignore")
      return _parse_video_kv(current_text)
    except Exception:
      logger.exception(f"Не удалось прочитать текущий video config: {target_video}")
      return {}

  def _merge_video_configs(
    self, current: dict[str, str], template: dict[str, str]
  ) -> dict[str, str]:
    merged = current.copy()
    merged.update(template)
    return merged

  def _save_video_config(
    self, cfg_dir: Path, config: dict[str, str], steam_id: str
  ) -> None:
    target_video = cfg_dir / "cs2_video.txt"
    try:
      target_video.write_text(_render_video_kv(config), encoding="utf-8")
      logger.debug(f"Применена cs2_video.txt steam_id={steam_id}: {target_video}")
    except Exception:
      logger.exception(f"Не удалось записать cs2_video.txt: {target_video}")

  def block_steam_store(self) -> bool:
    try:
      content = self._read_hosts_file()
      if content is None:
        return False
      if self._has_steam_store_block(content):
        logger.debug("Блокировка store.steampowered.com уже присутствует в hosts")
        return True
      lines = content.splitlines(keepends=True)
      while lines and lines[-1].strip() == "":
        lines.pop()
      if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
      lines.append(STEAM_STORE_BLOCK_LINE + "\n")
      return self._write_hosts_file("".join(lines))
    except Exception:
      logger.exception("Не удалось заблокировать store.steampowered.com")
      return False

  def unblock_steam_store(self) -> bool:
    try:
      content = self._read_hosts_file()
      if content is None:
        return False
      if not self._has_steam_store_block(content):
        logger.debug("Блокировка store.steampowered.com отсутствует в hosts")
        return True
      lines = content.splitlines(keepends=True)
      filtered_lines = []
      for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
          filtered_lines.append(line)
          continue
        if (
          stripped == STEAM_STORE_BLOCK_LINE
          or stripped == "0.0.0.0\tstore.steampowered.com"
          or (stripped.startswith("0.0.0.0") and "store.steampowered.com" in stripped)
        ):
          continue
        filtered_lines.append(line)
      return self._write_hosts_file("".join(filtered_lines))
    except Exception:
      logger.exception("Не удалось разблокировать store.steampowered.com")
      return False

  def _read_hosts_file(self) -> str | None:
    if not HOSTS_PATH.exists():
      logger.error(f"Файл hosts не найден: {HOSTS_PATH}")
      return None
    try:
      return HOSTS_PATH.read_text(encoding="utf-8", errors="ignore")
    except Exception:
      logger.exception(f"Unable to read hosts file: {HOSTS_PATH}")
      return None

  def _write_hosts_file(self, content: str) -> bool:
    try:
      HOSTS_PATH.write_text(content, encoding="utf-8")
      logger.info("Файл hosts успешно обновлен")
      return True
    except Exception:
      logger.exception(f"Unable to write to hosts: {HOSTS_PATH}")
      return False

  def _has_steam_store_block(self, content: str) -> bool:
    for line in content.splitlines():
      stripped = line.strip()
      if not stripped or stripped.startswith("#"):
        continue
      if (
        stripped == STEAM_STORE_BLOCK_LINE
        or stripped == "0.0.0.0\tstore.steampowered.com"
        or (stripped.startswith("0.0.0.0") and "store.steampowered.com" in stripped)
      ):
        return True
    return False


def _parse_video_kv(text: str) -> dict[str, str]:
  m = re.search(r"VideoConfig\"\s*\{([\s\S]*?)\}", text, re.IGNORECASE)
  body = m.group(1) if m else text
  entries: dict[str, str] = {}
  for line in body.splitlines():
    line = line.strip()
    if not line or line.startswith("//"):
      continue
    mm = re.match(r"\"([^\"]+)\"\s*\"([^\"]*)\"", line)
    if mm:
      entries[mm.group(1)] = mm.group(2)
  return entries


def _render_video_kv(entries: dict[str, str]) -> str:
  lines = ['"VideoConfig"', "{"]
  for key, value in entries.items():
    lines.append(f'  "{key}"    "{value}"')
  lines.append("}")
  lines.append("")
  return "\n".join(lines)
