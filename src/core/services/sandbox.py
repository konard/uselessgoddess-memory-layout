import os
import re
import subprocess
from typing import List
from core.logging import get_logger
from constants import SANDBOX_PATH

logger = get_logger("sv.sandboxie")


class SandboxieService:
  def __init__(self):
    self.start_path = os.path.join(SANDBOX_PATH, "Start.exe")
    self.ini_tool = os.path.join(SANDBOX_PATH, "SbieIni.exe")

  @staticmethod
  def sanitize_box_name(login: str) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9]", "_", login)
    clean_name = re.sub(r"_+", "_", clean_name)
    if len(clean_name) > 25:
      clean_name = clean_name[:25]
    return clean_name

  def create_box_if_not_exists(self, box_name: str) -> bool:
    if not os.path.exists(self.ini_tool):
      logger.error(f"SbieIni.exe not found at {self.ini_tool}")
      return False

    if self._box_exists(box_name):
      return True

    logger.info(f"Creating new sandbox for: [{box_name}]")

    settings = [
      ("Enabled", "y"),  # Включить бокс
      ("ConfigLevel", "10"),  # Версия конфига (актуальная для Plus)
      (
        "AutoRecover",
        "n",
      ),  # Отключить "Восстановление файлов" (чтобы не спамило окнами)
      ("BlockNetworkFiles", "n"),  # Разрешить сетевые диски (на всякий случай)
      ("RecoverFolder", "%Personal%"),  # Сброс путей восстановления
      ("RecoverFolder", "%Desktop%"),
      (
        "BorderColor",
        "#00FFFF,off,6",
      ),  # Визуальная рамка (Cyan), чтобы видеть изоляцию
      (
        "BoxNameTitle",
        "n",
      ),  # Не добавлять [#] в заголовки окон (для совместимости с FindWindow)
      ("BoxNameTitle", "-"),
      ("OpenPipePath", r"\Device\NamedPipe\SteamProtobufPipe"),
      ("OpenProcessAccess", "y"),
      ("OpenProcess", "steam.exe"),
      #
      ("AutoDelete", "y"),
      ("AutoRecover", "n"),
      ("NeverDelete", "n"),
      ("CopyLimitKb", "81920"),
      # Важно: Не создаем виртуальных дисков, используем стандартное перенаправление
    ]

    for key, val in settings:
      if not self._run_ini_command("set", box_name, key, val):
        logger.error(f"Failed to set sandbox setting: {key}={val}")
        return False

    self._reload_config()

    return True

  def build_command(
    self, box_name: str, executable: str, args: List[str]
  ) -> List[str]:
    cmd = [self.start_path, f"/box:{box_name}", "/silent", executable]
    cmd.extend(args)
    return cmd

  def _box_exists(self, box_name: str) -> bool:
    try:
      cmd = [self.ini_tool, "query", box_name, "Enabled"]
      result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )

      output = result.stdout.strip().lower()

      if result.returncode == 0 and output in ("y", "n"):
        return False

      return False
    except Exception:
      return False

  def _run_ini_command(
    self, action: str, box_name: str, setting: str, value: str = None
  ) -> bool:
    try:
      args = [self.ini_tool, action, box_name, setting]
      if value:
        args.append(value)

      result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )
      return result.returncode == 0
    except Exception as e:
      logger.error(f"SbieIni error: {e}")
      return False

  def _reload_config(self):
    try:
      kmd_util = os.path.join(self.base_dir, "KmdUtil.exe")
      if os.path.exists(kmd_util):
        subprocess.run(
          [kmd_util, "config", "reload"],
          creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
      pass
