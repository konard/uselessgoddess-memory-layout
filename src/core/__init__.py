"""Core utilities: config manager, logger, event bus, root filesystem."""

# Экспортируем синглтон root_fs, чтобы можно было писать `from src.core import root_fs`
from .root_fs import root_fs  # noqa: F401



