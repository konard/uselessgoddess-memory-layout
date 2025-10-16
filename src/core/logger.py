from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

logging.TRACE = 5


def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kwargs)


logging.Logger.trace = trace
logging.addLevelName(logging.TRACE, "TRACE")


def get_logger(name: str = "yacs") -> logging.Logger:
    logger = logging.getLogger(name)

    logger.setLevel(logging.TRACE)

    has_file_handler = any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
    if not has_file_handler:
        try:
            file_handler = RotatingFileHandler(
                filename=os.path.abspath("yacs.log"),
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.TRACE)  # Все уровни в файл
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.TRACE)
            console_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(console_handler)

        except Exception as e:
            print(f"Ошибка настройки логгера: {e}")
            logging.basicConfig(level=logging.TRACE)
            logger = logging.getLogger(name)
    else:
        pass
    return logger


