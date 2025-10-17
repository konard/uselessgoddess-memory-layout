from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6 import uic
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable
from PyQt6.QtWidgets import QMainWindow

from src.core.config_manager import ConfigManager
from src.core.event_bus import EventBus
from src.app.settings_window import SettingsWindow
from src.app.log_view import LogView
from src.app.accounts_tree_view import AccountsTreeView
from src.core.app_state import get_app_state


class LongTaskSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)


class LongTask(QRunnable):
    """Пример длительной задачи, безопасно обновляющей GUI через сигналы."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.signals = LongTaskSignals()
        self._message = message

    def run(self) -> None:  # type: ignore[override]
        # Имитация долгой операции
        import time

        for step in range(3):
            time.sleep(0.7)
            self.signals.progress.emit(f"Шаг {step + 1}/3: {self._message}")
        self.signals.finished.emit("Готово")


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    def __init__(self, config: ConfigManager, event_bus: EventBus, logger, parent: Optional[QMainWindow] = None) -> None:
        super().__init__(parent)
        self.config = config
        self.event_bus = event_bus
        self.logger = logger
        self.thread_pool = QThreadPool.globalInstance()

        ui_path = Path(__file__).resolve().parents[1] / "ui" / "main_window.ui"
        uic.loadUi(str(ui_path), self)

        # Инициализация вьюшек
        self.log_view = LogView(self.txtLogs, self.cbLogLevel, self.leLogFilter)
        self.accounts_view = AccountsTreeView(self.treeAccounts)

        # Подключение сигналов кнопок
        self.btnStartFarm.clicked.connect(self.start_farm)
        self.btnStartBattle.clicked.connect(self.start_battle)
        self.btnSettings.clicked.connect(self.open_settings)
        self.btnClearLogs.clicked.connect(self._clear_logs)

        # Динамическая фильтрация логов
        self.cbLogLevel.currentTextChanged.connect(self._render_logs)
        self.leLogFilter.textChanged.connect(self._render_logs)

        # Заполним список аккаунтов из AppState
        try:
            state = get_app_state()
            self.accounts_view.set_accounts(state.accounts)
        except Exception:
            pass


    def _run_long_task(self, label: str) -> None:
        task = LongTask(label)
        task.signals.progress.connect(self._on_task_progress)
        task.signals.finished.connect(self._on_task_finished)
        self.thread_pool.start(task)

    def _on_task_progress(self, text: str) -> None:
        self.lblStatus.setText(text)
        self.event_bus.emit("task_progress", text=text)

    def _on_task_finished(self, text: str) -> None:
        self.lblStatus.setText(text)
        self.event_bus.emit("task_finished", text=text)

    def start_farm(self) -> None:
        """Заглушка старта фарма: логирует и меняет статус."""
        self.logger.trace("Запуск заглушки фарма")
        self.lblStatus.setText("Фарм: запускается...")
        self.event_bus.emit("start_farm")
        self._run_long_task("Фарм")

    def start_battle(self) -> None:
        """Заглушка старта боя: логирует и меняет статус."""
        self.logger.trace("Запуск заглушки боя")
        self.lblStatus.setText("Бой: запускается...")
        self.event_bus.emit("start_battle")
        self._run_long_task("Бой")

    def open_settings(self) -> None:
        """Открывает окно настроек и сохраняет результат через ConfigManager."""
        self.logger.debug("Открываю окно настроек")
        dialog = SettingsWindow(config=self.config, parent=self)
        if dialog.exec():  # OK
            self.logger.trace("Настройки сохранены")
            self.lblStatus.setText("Настройки сохранены")
        else:
            self.logger.debug("Настройки отменены пользователем")

    # ----- Плагины UI (панель слева) -----
    def add_plugin_button(self, text: str, on_clicked) -> None:
        """Публичный метод для плагинов: добавить кнопку на левую панель."""
        from PyQt6.QtWidgets import QPushButton

        btn = QPushButton(text)
        btn.clicked.connect(on_clicked)
        self.layoutPlugins.insertWidget(self.layoutPlugins.count() - 1, btn)

    # ----- Логи -----
    def append_log(self, message: str, level: str) -> None:
        # Всегда добавляем в буфер, отображаем согласно текущему фильтру
        self.log_view.append(message, level)

    def _render_logs(self) -> None:
        self.log_view.render()

    def _clear_logs(self) -> None:
        self.log_view.clear()


