from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from core.logging import get_logger


logger = get_logger("ConfigManager")
DEFAULT_CONFIG: Dict[str, Any] = {
    "accounts_file": "accounts.json",
    "steam_path": "",
    "cs2_path": "",
    "plugins": {"enabled": ["example_plugin"]},
}


class ConfigManager:
    """Менеджер конфигурации с атомарным сохранением и версионированием.

    Формат: JSON-файл на диске. При сохранении данные записываются во временный файл
    и затем атомарно переименовываются в целевой путь.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: Dict[str, Any] = DEFAULT_CONFIG.copy()

    # API
    def load(self) -> None:
        """Загружает конфиг с диска; если нет — создаёт структуру по умолчанию."""
        if not self._path.exists():
            logger.trace("Конфиг не найден, будет создан при сохранении: %s", self._path)
            self._ensure_parent()
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Некорректный формат config.json: ожидается объект JSON")
            self._data = {**DEFAULT_CONFIG, **data}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при загрузке конфига: %s", exc)
            self._data = DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Сохраняет конфиг атомарно (через временный файл и rename)."""
        self._ensure_parent()
        json_str = json.dumps(self._data, ensure_ascii=False, indent=2)
        dir_name = str(self._path.parent)
        fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".tmp", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json_str)
            os.replace(tmp_path, self._path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def _ensure_parent(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)


