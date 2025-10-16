from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

from PyQt6.QtWidgets import QApplication

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.event_bus import EventBus
from src.app.main_window import MainWindow
from src.core.gui_executor import GuiExecutor
from src.core.gui_log_handler import install_gui_log_handler
from src.core.app_state import init_app_state, get_app_state
from src.plugins.plugin_manager import PluginManager
from src.core.root_fs import root_fs


def main() -> NoReturn:
    app = QApplication(sys.argv)
    logger = get_logger("yacsp")
    logger.trace("Starting YACSP")
    config_path = Path(__file__).parent / "config" / "config.json"
    logger.trace(f"Loading config from {config_path}")
    config = ConfigManager(config_path)
    config.load()
    logger.trace("Config loaded")

    event_bus = EventBus()
    logger.trace("Event bus created")

    # Глобальный стейт
    state = init_app_state(config=config, event_bus=event_bus)
    logger.trace("AppState created")
    window = MainWindow(config=config, event_bus=event_bus, logger=logger)
    window.show()
    logger.trace("Window shown")
    gui_exec = GuiExecutor()
    install_gui_log_handler(window.append_log)
    logger.trace("GUI log handler installed")

    state.window = window
    state.gui_exec = gui_exec
    plugin_manager = PluginManager()
    logger.trace("Plugin manager created")
    enabled_plugins = config.get("plugins", {}).get("enabled", [])
    if not isinstance(enabled_plugins, list):
        enabled_plugins = []
    plugin_manager.load_enabled(enabled_plugins, state.as_context())
    logger.trace("Plugins loaded")
    window.plugin_manager = plugin_manager  # type: ignore[attr-defined]
    state.plugin_manager = plugin_manager

    # Применяем базовые стили (если файл есть)
    try:
        style_path = root_fs.resolve("src/resources/styles.qss")
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
    except Exception:
        pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()


