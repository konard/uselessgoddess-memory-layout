from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import cast

FATAL = 50
ERROR = 40
WARN = 30
INFO = 20
DEBUG = 10
TRACE = 5


class Logger(logging.Logger):
  def warn(self, message, *args, **kwargs):
    if self.isEnabledFor(WARN):
      self._log(WARN, message, args, **kwargs)
  
  def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE):
      self._log(TRACE, message, args, **kwargs)

logging.addLevelName(TRACE, "TRACE")
logging.setLoggerClass(Logger)


def setup_logger(name: str) -> logging.Logger:
  logger = logging.getLogger(name)

  logger.setLevel(TRACE)

  has_file_handler = any(
    isinstance(h, RotatingFileHandler) for h in logger.handlers
  )
  if not has_file_handler and not logger.hasHandlers():
    try:
      file_handler = RotatingFileHandler(
        filename=os.path.abspath("yacs.log"),
        backupCount=3,
        encoding="utf-8",
      )
      file_handler.setLevel(TRACE)
      file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
      )
      logger.addHandler(file_handler)

      console_handler = logging.StreamHandler()
      console_handler.setLevel(TRACE)
      console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
      )
      logger.addHandler(console_handler)

    except Exception as e:
      print(f"Logger setup error: {e}")
      logging.basicConfig(level=TRACE)
      logger = logging.getLogger(name)
  else:
    pass
  return logger


def get_logger(name: str) -> Logger:
  return cast(Logger, setup_logger(name))
