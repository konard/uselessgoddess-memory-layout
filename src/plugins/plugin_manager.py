from __future__ import annotations

import importlib
import pkgutil

from core.logging import get_logger

from . import PluginBase


class PluginManager:
  """Менеджер плагинов: обнаружение, безопасная загрузка и управление жизненным циклом."""

  def __init__(self, plugins_package: str = "plugins.available") -> None:
    self._logger = get_logger("PluginManager")
    self._plugins_package = plugins_package
    self._loaded: dict[str, PluginBase] = {}

  def discover(self) -> list[str]:
    """Возвращает список доступных пакетов плагинов (имён пакетов)."""
    try:
      package = importlib.import_module(self._plugins_package)
    except Exception as exc:
      self._logger.exception("Не удалось импортировать пакет плагинов: %s", exc)
      return []

    names: list[str] = []
    for module_info in pkgutil.iter_modules(package.__path__):  # type: ignore[attr-defined]
      if module_info.ispkg:
        names.append(module_info.name)
    return names

  def load_enabled(
    self, enabled_names: list[str], app_context: dict[str, object]
  ) -> None:
    """Загружает и инициализирует включённые плагины.

    enabled_names: список имён пакетов (напр. ["example_plugin"]).
    app_context: контекст приложения, доступный плагинам.
    """
    for name in enabled_names:
      self._safe_load(name, app_context)

  def _safe_load(self, name: str, app_context: dict[str, object]) -> None:
    fq_name = f"{self._plugins_package}.{name}.plugin"
    try:
      module = importlib.import_module(fq_name)
      plugin_obj = getattr(module, "plugin", None)
      if plugin_obj is None or not hasattr(plugin_obj, "setup"):
        self._logger.error(
          "Плагин '%s' не экспортирует объект 'plugin' совместимый с PluginBase",
          name,
        )
        return
      plugin: PluginBase = plugin_obj
      plugin.setup(app_context)
      self._loaded[name] = plugin
      self._logger.trace("Плагин '%s' загружен", name)
    except Exception as exc:
      self._logger.exception("Ошибка загрузки плагина '%s': %s", name, exc)

  def unload_all(self) -> None:
    for name, plugin in list(self._loaded.items()):
      try:
        plugin.teardown()
      except Exception as exc:
        self._logger.exception("Ошибка выключения плагина '%s': %s", name, exc)
      finally:
        self._loaded.pop(name, None)

  @property
  def loaded_plugins(self) -> dict[str, PluginBase]:
    return dict(self._loaded)
