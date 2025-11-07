"""
ProcessService - сервис для управления процессами
Отвечает за запуск, остановку и мониторинг процессов
"""

import os
import psutil
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
