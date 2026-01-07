"""
ConfigService - применение конфигураций CS2

1) Копирует settings/yacs.cfg в <csgo_path>\game\csgo\cfg при отсутствии.
   Дополнительно обеспечивает autoexec.cfg с "exec yacs.cfg".

2) Применяет video.txt из settings/video.txt в файл профиля:
   <userdata>/<steam_id>/730/local/cfg/video.txt. Создаёт недостающие папки.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import stat
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

# Константы для работы с hosts файлом
HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
STEAM_STORE_BLOCK_LINE = "0.0.0.0 store.steampowered.com"

# Глобальная переменная для хранения контекста при закрытии
_cleanup_context: Context | None = None


def _cleanup_steam_store_block():
  """Функция очистки блокировки Steam Store при закрытии приложения."""
  if _cleanup_context is None:
    return

  try:
    config_service = ConfigService(_cleanup_context)
    config_service.unblock_steam_store()
  except Exception:
    # Игнорируем ошибки при очистке, чтобы не мешать закрытию приложения
    pass


# Регистрируем функцию очистки при выходе из программы
atexit.register(_cleanup_steam_store_block)


class ConfigService:
  """Сервис для применения конфигураций CS2."""

  def __init__(self, ctx: Context) -> None:
    self.ctx = ctx
    # Регистрируем контекст для очистки при закрытии
    global _cleanup_context
    _cleanup_context = ctx

  def ensure_cs_cfgs(self) -> None:
    """Обеспечивает наличие конфигурационных файлов CS2 и удаляет panorama/videos."""
    csgo_path = Path(self.ctx.s.u.cs_path)
    cfg_dir = csgo_path / "game" / "csgo" / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    self._copy_config_files(cfg_dir)

  def apply_video_config(self, steam_id: str) -> None:
    """Применяет видео конфигурацию для указанного Steam ID."""
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

    for target_cfg_dir in target_cfg_dirs:
      self._copy_file_if_exists(
        CS2_MACHINE_CONVARS_SRC,
        target_cfg_dir / "cs2_machine_convars.vcfg",
        "cs2_machine_convars.vcfg",
      )
      current_kv = self._load_current_video_config(target_cfg_dir)
      merged_kv = self._merge_video_configs(current_kv, template_kv)
      self._save_video_config(target_cfg_dir, merged_kv, steam_id)

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
    """Копирует конфигурационные файлы в директорию CS2."""
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
    """Копирует файл, если исходный файл существует."""
    if not src.exists():
      return

    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    logger.debug(f"Обновлен `{file_name}` -> `{dst}`")

  def _find_userdata_dir(self) -> Path:
    """Находит директорию userdata Steam."""
    steam_path = self.ctx.s.u.steam_path
    steam_dir = Path(steam_path).parent

    candidates = [
      steam_dir / "userdata",
      steam_dir.parent / "userdata",
    ]

    for candidate in candidates:
      if candidate.exists() or (not candidate.exists() and candidate.parent.exists()):
        return candidate

    # Fallback: возвращаем предполагаемую директорию
    return steam_dir / "userdata"

  def _ensure_cfg_directories(self, userdata_dir: Path, steam_id: str) -> list[Path]:
    """Создает директории конфигурации (local и remote) для указанного Steam ID."""
    base_dir = userdata_dir / str(steam_id) / "730"
    targets = [
      base_dir / "local" / "cfg",
      # base_dir / "remote" / "cfg",
    ]
    created = []
    for target in targets:
      try:
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)
      except Exception:
        logger.exception(f"Не удалось создать каталог: {target}")
    return created

  def _load_video_template(self) -> dict[str, str] | None:
    """Загружает шаблон видео конфигурации."""
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
    """Загружает текущую видео конфигурацию, если она существует."""
    target_video = cfg_dir / "video.txt"
    if not target_video.exists():
      return {}

    try:
      current_text = target_video.read_text(encoding="utf-8", errors="ignore")
      return _parse_video_kv(current_text)
    except Exception:
      logger.exception(f"Не удалось прочитать текущий video.txt: {target_video}")
      return {}

  def _merge_video_configs(
    self, current: dict[str, str], template: dict[str, str]
  ) -> dict[str, str]:
    """Объединяет текущую и шаблонную конфигурации (шаблон имеет приоритет)."""
    merged = current.copy()
    merged.update(template)
    return merged

  def _save_video_config(
    self, cfg_dir: Path, config: dict[str, str], steam_id: str
  ) -> None:
    """Сохраняет видео конфигурацию в файл."""
    target_video = cfg_dir / "cs2_video.txt"
    try:
      target_video.write_text(_render_video_kv(config), encoding="utf-8")
      logger.debug(f"Применена cs2_video.txt steam_id={steam_id}: {target_video}")
    except Exception:
      logger.exception(f"Не удалось записать cs2_video.txt: {target_video}")

  def block_steam_store(self) -> bool:
    """Добавляет блокировку store.steampowered.com в файл hosts."""
    try:
      content = self._read_hosts_file()
      if content is None:
        return False

      # Проверяем, есть ли уже эта строка
      if self._has_steam_store_block(content):
        logger.debug("Блокировка store.steampowered.com уже присутствует в hosts")
        return True

      # Добавляем строку в конец файла
      lines = content.splitlines(keepends=True)
      # Убираем лишние пустые строки в конце
      while lines and lines[-1].strip() == "":
        lines.pop()

      # Добавляем блокировку
      if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
      lines.append(STEAM_STORE_BLOCK_LINE + "\n")

      new_content = "".join(lines)
      return self._write_hosts_file(new_content)

    except Exception:
      logger.exception("Не удалось заблокировать store.steampowered.com")
      return False

  def unblock_steam_store(self) -> bool:
    """Удаляет блокировку store.steampowered.com из файла hosts."""
    try:
      content = self._read_hosts_file()
      if content is None:
        return False

      # Проверяем, есть ли эта строка
      if not self._has_steam_store_block(content):
        logger.debug("Блокировка store.steampowered.com отсутствует в hosts")
        return True

      # Удаляем строку с блокировкой
      lines = content.splitlines(keepends=True)
      filtered_lines = []
      for line in lines:
        # Пропускаем строку с блокировкой
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
          filtered_lines.append(line)
          continue
        # Проверяем различные варианты записи блокировки
        if (
          stripped == STEAM_STORE_BLOCK_LINE
          or stripped == "0.0.0.0\tstore.steampowered.com"
          or (stripped.startswith("0.0.0.0") and "store.steampowered.com" in stripped)
        ):
          continue
        filtered_lines.append(line)

      new_content = "".join(filtered_lines)
      return self._write_hosts_file(new_content)

    except Exception:
      logger.exception("Не удалось разблокировать store.steampowered.com")
      return False

  def _read_hosts_file(self) -> str | None:
    """Читает содержимое файла hosts."""
    if not HOSTS_PATH.exists():
      logger.error(f"Файл hosts не найден: {HOSTS_PATH}")
      return None

    try:
      return HOSTS_PATH.read_text(encoding="utf-8", errors="ignore")
    except PermissionError:
      logger.error("REPORT IF THIS HAPPENS!")
      return None
    except Exception:
      logger.exception(f"Unable to read hosts file: {HOSTS_PATH}")
      return None

  def _write_hosts_file(self, content: str) -> bool:
    try:
      HOSTS_PATH.write_text(content, encoding="utf-8")
      logger.info("Файл hosts успешно обновлен")
      return True
    except PermissionError:
      logger.error("REPORT IF THIS HAPPENS!")
      return False
    except Exception:
      logger.exception(f"Unable to write to hosts: {HOSTS_PATH}")
      return False

  def _has_steam_store_block(self, content: str) -> bool:
    """Проверяет, присутствует ли блокировка store.steampowered.com в содержимом."""
    for line in content.splitlines():
      stripped = line.strip()
      # Пропускаем комментарии и пустые строки
      if not stripped or stripped.startswith("#"):
        continue
      # Проверяем точное совпадение или строки вида "IP store.steampowered.com"
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
      key, value = mm.group(1), mm.group(2)
      entries[key] = value
  return entries


def _render_video_kv(entries: dict[str, str]) -> str:
  lines = ['"VideoConfig"', "{"]
  for key, value in entries.items():
    lines.append(f'  "{key}"    "{value}"')
  lines.append("}")
  lines.append("")
  return "\n".join(lines)
