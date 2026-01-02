import ctypes
import os
import re
import subprocess

from constants import PROJECT_ROOT
from core.logging import get_logger

logger = get_logger("terminator")

HANDLE_TOOL_NAME = "handle64.exe"
TARGET_PROCESS = "cs2.exe"
MUTEX_PATTERN = "singleton_mutex"


def is_admin():
  """Проверка прав администратора"""
  try:
    return ctypes.windll.shell32.IsUserAnAdmin()
  except Exception:
    return False


def close_cs2_mutex() -> bool:
  """
  Ищет процессы CS2 и закрывает мьютексы одиночного запуска (Singleton),
  используя утилиту Sysinternals handle64.exe.
  """

  handle_path = os.path.join(PROJECT_ROOT, "data", HANDLE_TOOL_NAME)

  if not os.path.exists(handle_path):
    logger.error(f"Handle tool not found! Expected at: {handle_path}")
    return False

  logger.debug(f"Start scanning mutexes for {TARGET_PROCESS} via {HANDLE_TOOL_NAME}...")

  cmd_list = [handle_path, "-a", "-p", TARGET_PROCESS, "-nobanner", "-accepteula"]

  try:
    result = subprocess.run(
      cmd_list,
      capture_output=True,
      stdin=subprocess.DEVNULL,
    )
  except Exception as e:
    logger.error(f"Failed to run handle64: {e}")
    return False

  if result.returncode != 0 and not result.stdout:
    logger.debug("No handles returned (CS2 might not be running).")
    return True

  stdout_text = result.stdout.decode("utf-8", errors="replace")
  lines = stdout_text.splitlines()
  targets_to_kill = []
  current_pid = None

  pid_regex = re.compile(r"pid:\s*(\d+)", re.IGNORECASE)
  handle_regex = re.compile(r"^\s*([0-9A-Fa-f]+):\s+Mutant\s+(.*)", re.IGNORECASE)

  # 3. Парсим вывод
  for line in lines:
    # Ищем смену PID (новый процесс в списке)
    if TARGET_PROCESS in line:
      pid_match = pid_regex.search(line)
      if pid_match:
        current_pid = pid_match.group(1)
      continue

    # Внутри блока процесса ищем нужный мьютекс
    if current_pid:
      match = handle_regex.search(line)
      if match:
        hex_id = match.group(1)
        name = match.group(2).strip()

        if MUTEX_PATTERN.lower() in name.lower():
          logger.debug(
            f"Found mutex to kill: PID={current_pid}, Handle={hex_id}, Name={name}"
          )
          targets_to_kill.append({"pid": current_pid, "handle": hex_id})

  if not targets_to_kill:
    logger.debug("No singleton mutexes found (already clean or game not running).")
    return True

  # 4. Закрываем найденные мьютексы
  success_count = 0
  for target in targets_to_kill:
    close_cmd = [
      handle_path,
      "-c",
      target["handle"],
      "-p",
      target["pid"],
      "-y",  # Yes (без подтверждения)
      "-nobanner",
      "-accepteula",
    ]

    try:
      res = subprocess.run(
        close_cmd,
        capture_output=True,
        text=True,
      )

      if res.returncode == 0:
        success_count += 1
      else:
        logger.warn(
          f"Failed to close handle {target['handle']} \n"
          f"for PID {target['pid']}: {res.stdout.strip()}"
        )
    except Exception as e:
      logger.error(f"Exception while closing handle: {e}")

  logger.trace(f"Mutex cleanup finished. Closed: {success_count}/{len(targets_to_kill)}")

  # Возвращаем True, если удалось закрыть всё, что нашли
  return success_count == len(targets_to_kill)


if __name__ == "__main__":
  if not is_admin():
    print("[-] Error: This script requires Administrator privileges!")
  else:
    if close_cs2_mutex():
      print("[+] Success: Mutexes processed.")
    else:
      print("[-] Finished with errors or file not found.")
