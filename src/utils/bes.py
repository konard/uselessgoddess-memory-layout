import asyncio
import builtins
import contextlib

import psutil

from core.logging import get_logger

logger = get_logger("bes")

TARGETS_CONFIG = {
  "cs2.exe": 92,  # Оставляем 8% жизни
  "steam.exe": 90,  # Оставляем 10% жизни (нужно для сети)
  "steamwebhelper.exe": 98,  # Убиваем почти в ноль (браузер стима)
}

CYCLE_DURATION = 0.1  # Длительность цикла (сек). 0.1 = 100мс


class BesService:
  """Сервис для ограничения CPU процессов (BES - Battle Encoder Shirase аналог)."""

  def __init__(self):
    self._running = False
    self._managed_procs = {}

  async def start(self):
    """Запустить сервис."""
    if self._running:
      return

    self._running = True
    logger.info("BesService started")
    asyncio.create_task(self._check_loop())

  def stop(self):
    """Остановить сервис."""
    self._running = False
    logger.info("BesService stopping...")

  async def _limit_logic(self, proc_obj, limit_percent):
    """
    Математика цикла:
    Если limit 90%, цикл 100мс:
    90мс спим (suspend), 10мс работаем (resume).
    """
    if limit_percent > 99:
      limit_percent = 99
    if limit_percent < 1:
      limit_percent = 1

    sleep_time = CYCLE_DURATION * (limit_percent / 100.0)
    work_time = CYCLE_DURATION - sleep_time

    try:
      # ЗАМОРОЗКА
      proc_obj.suspend()
      await asyncio.sleep(sleep_time)

      # РАЗМОРОЗКА
      proc_obj.resume()
      await asyncio.sleep(work_time)
      return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
      return False

  async def _check_loop(self):
    try:
      while self._running:
        for p in psutil.process_iter(["pid", "name"]):
          try:
            p_name = p.info["name"].lower()
            p_pid = p.info["pid"]

            if p_name in TARGETS_CONFIG and p_pid not in self._managed_procs:
              self._managed_procs[p_pid] = {
                "proc": p,
                "limit": TARGETS_CONFIG[p_name],
              }
          except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        if not self._managed_procs:
          # logger.debug("Waiting for processes...")
          await asyncio.sleep(1)
          continue

        # Проходим по списку и душим
        for pid, data in list(self._managed_procs.items()):
          if not self._running:
            break

          proc = data["proc"]
          limit = data["limit"]

          alive = await self._limit_logic(proc, limit)

          if not alive:
            del self._managed_procs[pid]

        # Небольшая пауза чтобы не грузить цикл если пусто,
        # но у нас и так sleep внутри limit_logic, так что тут минимально или 0
        await asyncio.sleep(0)

    except asyncio.CancelledError:
      logger.info("BesService cancelled")
    except Exception as e:
      logger.error(f"Error in BesService: {e}")
    finally:
      self._cleanup()

  def _cleanup(self):
    """Разморозить все процессы перед выходом."""
    logger.info("Cleaning up managed processes...")
    for _, data in self._managed_procs.items():
      with contextlib.suppress(builtins.BaseException):
        data["proc"].resume()
    self._managed_procs.clear()
