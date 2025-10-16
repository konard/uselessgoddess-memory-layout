CS2 Helper — каркас приложения на PyQt6

Этот репозиторий — стартовый шаблон для настольного приложения на Python 3.11+ и PyQt6 с модульной архитектурой, конфигурацией, плагинами и базовыми инструментами качества кода (pytest, mypy, black). Игровой логики здесь нет — только архитектурный каркас.

## Возможности
- Главный экран `MainWindow` с кнопками запуска заглушек и перехода к настройкам.
- Окно настроек `SettingsWindow` для выбора путей Steam и CS2.
- Надёжный `ConfigManager` с атомарным сохранением и версионированием.
- `EventBus` для обмена событиями между модулями.
- Плагины через `PluginManager` c примером плагина.
- Примеры фоновых задач (`QThreadPool`/`QRunnable`) с безопасным обновлением GUI через сигналы.
- Тесты `pytest` и CI (GitHub Actions) для `pytest`, `mypy`, `black --check`.

## Структура проекта
```
cs2_helper/
├─ README.md
├─ pyproject.toml
├─ requirements.txt
├─ .gitignore
├─ main.py
├─ config/
│  └─ example_config.json
├─ src/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main_window.py
│  │  └─ settings_window.py
│  ├─ core/
│  │  ├─ __init__.py
│  │  ├─ config_manager.py
│  │  ├─ logger.py
│  │  └─ event_bus.py
│  ├─ plugins/
│  │  ├─ __init__.py
│  │  ├─ plugin_manager.py
│  │  ├─ available/
│  │  │  ├─ __init__.py
│  │  │  └─ example_plugin/
│  │  │     ├─ __init__.py
│  │  │     └─ plugin.py
│  ├─ ui/
│  │  ├─ main_window.ui
│  │  └─ settings_window.ui
│  └─ resources/
│     └─ icons/
├─ tests/
│  ├─ test_config.py
│  └─ test_plugin_manager.py
└─ .github/
   └─ workflows/
      └─ ci.yml
```

## Быстрый старт
1) Python 3.11+
2) Создать и активировать виртуальное окружение.

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux (bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3) Установка зависимостей:
```bash
pip install -r requirements.txt
```

4) Запуск приложения:
```bash
python main.py
```

Первый запуск создаст файл `config/config.json` при сохранении настроек.

## Работа с UI (.ui)
- Файлы `src/ui/*.ui` открываются в Qt Designer (часть Qt или `pip install pyqt6-tools` для локального Designer).
- Можно использовать загрузку через `PyQt6.uic.loadUi` (уже реализовано). Альтернатива — скомпилировать формы:
```bash
pyuic6 -o src/app/ui_main_window.py src/ui/main_window.ui
pyuic6 -o src/app/ui_settings_window.py src/ui/settings_window.ui
```
И далее импортировать полученные Python-модули вместо динамической загрузки.

## Плагины
Плагины располагаются в `src/plugins/available/<plugin_package>` и должны предоставлять класс, совместимый с интерфейсом `PluginBase`.

Интерфейс `PluginBase` (сокр.):
```python
class PluginBase(Protocol):
    def setup(self, app_context: dict) -> None: ...
    def teardown(self) -> None: ...
    @property
    def meta(self) -> dict: ...
```

Включение/отключение плагинов управляется конфигом (`plugins.enabled`: список строк `package_name`), см. `config/config.json`.

Пример: `src/plugins/available/example_plugin/plugin.py`.

## EventBus API
```python
event_bus.subscribe("task_started", callback)
event_bus.emit("task_started", task_id="demo")
```
Подписчики вызываются безопасно, исключения логируются.

## ConfigManager
- Формат JSON, атомарное сохранение (временный файл + rename).
- Версионирование через поле `config_version` и `migrate_if_needed()`.
- Ключи по умолчанию: `steam_path`, `cs2_path`, `plugins`.

## Pre-commit (рекомендовано)
Установить и активировать хуки:
```bash
pip install pre-commit
pre-commit install
```
Добавьте в `.pre-commit-config.yaml` хуки `black`, `flake8`, `mypy` при необходимости.

## Проверки качества
```bash
pytest
mypy src
black --check .
```

## Как добавить новый плагин
1. Создайте пакет `src/plugins/available/my_plugin/` с `__init__.py` и файлом `plugin.py`.
2. Реализуйте класс с методами `setup(app_context)`, `teardown()` и свойством `meta`.
3. Добавьте имя пакета `my_plugin` в список `plugins.enabled` в конфиге.
4. Перезапустите приложение — менеджер плагинов загрузит плагин.

## Как подключить новую .ui форму
1. Создайте файл `.ui` в `src/ui/` (Qt Designer). Убедитесь, что `objectName` виджетов совпадают с кодом.
2. В соответствующем окне используйте `uic.loadUi(path, self)` или скомпилируйте форму `pyuic6` и импортируйте класс.
3. Подключите сигналы/слоты к логике в Python-коде.

## Лицензия и безопасность
Шаблон не содержит и не должен содержать функциональность, облегчающую вмешательство в клиент игры, инжекцию, обход античитов и т.п. Только UI, конфигурация и плагинная архитектура.


