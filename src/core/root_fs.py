from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Iterable, Optional, TextIO

from core.logging import get_logger


_ROOT_LOGGER = get_logger("RootFS")


def _find_upwards(start: Path, markers: Iterable[str]) -> Optional[Path]:
    current = start
    markers_set = set(markers)
    for _ in range(10):  # ограничим подъём по дереву
        if any((current / m).exists() for m in markers_set):
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def detect_project_root() -> Path:
    """Определяет корень проекта.

    Приоритет:
    1) env PROJECT_ROOT
    2) поиск вверх от текущего файла по маркерам (pyproject.toml, .git, requirements.txt)
    3) текущая рабочая директория
    """

    env_root = os.getenv("PROJECT_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if p.exists():
            _ROOT_LOGGER.debug("PROJECT_ROOT=%s", p)
            return p

    module_dir = Path(__file__).resolve().parent
    candidate = _find_upwards(module_dir, ["pyproject.toml", ".git", "requirements.txt"])  # type: ignore[list-item]
    if candidate is not None:
        _ROOT_LOGGER.debug("Detected root via markers: %s", candidate)
        return candidate

    _ROOT_LOGGER.debug("Fallback to cwd() as project root")
    return Path.cwd().resolve()


class RootFS:
    """Файловая система, привязанная к корню проекта.

    Все методы принимают относительные пути относительно корня проекта.
    Поддерживает безопасную запись (atomic save) через временный файл.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = (root or detect_project_root()).resolve()

    def resolve(self, relative: os.PathLike[str] | str) -> Path:
        path = (self.root / Path(relative)).resolve()
        if not str(path).startswith(str(self.root)):
            raise ValueError("Попытка выйти за пределы корня проекта")
        return path

    # ----- чтение -----
    def open_text(self, relative: os.PathLike[str] | str, mode: str = "r", encoding: str = "utf-8") -> TextIO:
        if "b" in mode:
            raise ValueError("Для бинарного режима используйте open_binary")
        return self.resolve(relative).open(mode, encoding=encoding)

    def open_binary(self, relative: os.PathLike[str] | str, mode: str = "rb"):
        if "b" not in mode:
            raise ValueError("Для текстового режима используйте open_text")
        return self.resolve(relative).open(mode)

    def read_text(self, relative: os.PathLike[str] | str, encoding: str = "utf-8") -> str:
        with self.open_text(relative, "r", encoding=encoding) as f:
            return f.read()

    def read_json(self, relative: os.PathLike[str] | str, encoding: str = "utf-8"):
        text = self.read_text(relative, encoding=encoding)
        return json.loads(text)

    # ----- запись (атомарная) -----
    def write_text_atomic(self, relative: os.PathLike[str] | str, data: str, encoding: str = "utf-8") -> Path:
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        dir_name = str(target.parent)
        fd, tmp_path = tempfile.mkstemp(prefix="rootfs_", suffix=".tmp", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding=encoding) as f:
                f.write(data)
            os.replace(tmp_path, target)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        return target

    def write_json_atomic(self, relative: os.PathLike[str] | str, obj) -> Path:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        return self.write_text_atomic(relative, text)

    # ----- утилиты -----
    def exists(self, relative: os.PathLike[str] | str) -> bool:
        return self.resolve(relative).exists()


# Singleton по умолчанию
root_fs = RootFS()


