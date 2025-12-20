import os
from typing import List
import psutil
import subprocess
from core.logging import get_logger

logger = get_logger("yacs.process")


class ProcessService:
  """Сервис для управления процессами"""

  @staticmethod
  def kill_by_pid(pid: int) -> bool:
    """Убить процесс по PID"""
    try:
      if pid > 0:
        os.kill(pid, 9)  # SIGKILL
        return True
    except (ProcessLookupError, OSError):
      pass
    return False

  @staticmethod
  def is_process_running(pid: int) -> bool:
    """Проверить, запущен ли процесс"""
    try:
      return psutil.pid_exists(pid)
    except Exception as e:
      logger.error(f"Error checking if process {pid} is running: {e}")
      return False

  @staticmethod
  def get_runner_pid(pid: int) -> int:
    """Получить PID Runner"""
    try:
      proc = psutil.Process(pid)
      for parent in proc.parents():
        if parent.name() == "cs2_runner.exe":
          return parent.pid
    except Exception as e:
      logger.error(f"Error getting runner PID for {pid}: {e}")
      return -1
    return -1

  @staticmethod
  def get_all_runner_pids() -> List[int]:
    return [
      proc.pid
      for proc in psutil.process_iter()
      if proc.name() == "cs2_runner.exe"
    ]

  @staticmethod
  def kill_all_runners() -> None:
    for pid in ProcessService.get_all_runner_pids():
      logger.info(f"Killing runner PID: {pid}")
      ProcessService.kill_by_pid(pid)

  @staticmethod
  def kill_sandboxie_processes(sandboxie_path: str) -> None:
    if not sandboxie_path or not os.path.exists(sandboxie_path):
      return

    try:
      logger.info("Terminating all sandbox processes...")
      subprocess.run(
        [sandboxie_path, "/terminate_all"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
      )
    except Exception as e:
      logger.error(f"Failed to terminate Sandboxie boxes: {e}")
