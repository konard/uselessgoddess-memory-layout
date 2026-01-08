import asyncio

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
  QComboBox,
  QGridLayout,
  QHBoxLayout,
  QMessageBox,
  QSpinBox,
  QVBoxLayout,
  QWidget,
)

from core.context import Context
from core.services.settings import InferenceDevice
from ui.theme import CURRENT_THEME, ButtonType
from ui.widgets import Button, Label, LabelType, Switch, TitledPanel


class AdvancedTab(QWidget):
  def __init__(self, ctx: Context, parent=None):
    super().__init__(parent)
    self.ctx = ctx
    self._setup_ui()
    self._load_values()

  def _setup_ui(self):
    grid = QGridLayout(self)
    grid.setAlignment(Qt.AlignmentFlag.AlignTop)
    grid.setSpacing(10)
    grid.setContentsMargins(10, 10, 10, 10)

    # === COLUMN 1: AI & HARDWARE ===
    ai_panel = TitledPanel("AI & Hardware")
    ai_layout = QVBoxLayout(ai_panel.container)
    ai_layout.setSpacing(10)

    # Device
    device_layout = QHBoxLayout()
    device_layout.addWidget(Label("Inference Device:"))
    self.combo_device = QComboBox()
    self.combo_device.addItems([d.value.upper() for d in InferenceDevice])
    self.combo_device.setStyleSheet(self._input_style())
    device_layout.addWidget(self.combo_device)
    ai_layout.addLayout(device_layout)

    # Threads
    threads_layout = QHBoxLayout()
    threads_layout.addWidget(Label("CPU Threads:"))
    self.spin_threads = QSpinBox()
    self.spin_threads.setRange(0, 32)
    self.spin_threads.setStyleSheet(self._input_style())
    threads_layout.addWidget(self.spin_threads)
    ai_layout.addLayout(threads_layout)

    # Reload Button (Manual Action)
    self.btn_reload_ai = Button(
      "Apply & Reload AI",
      on_click=self._apply_ai_settings,
      button_type=ButtonType.PRIMARY,
    )
    ai_layout.addWidget(self.btn_reload_ai)

    # Benchmark Section (Separator)
    ai_layout.addSpacing(15)
    ai_layout.addWidget(Label("Performance Test", LabelType.HEADER))

    self.lbl_bench_result = Label("-", LabelType.SECONDARY)
    ai_layout.addWidget(self.lbl_bench_result)

    self.btn_bench = Button(
      "Run Benchmark", on_click=self._run_benchmark, button_type=ButtonType.DEFAULT
    )
    ai_layout.addWidget(self.btn_bench)
    ai_layout.addStretch()  # Push content up

    # === COLUMN 2: MATCH LOGIC ===
    logic_panel = TitledPanel("Match Logic")
    logic_layout = QVBoxLayout(logic_panel.container)
    logic_layout.setSpacing(15)

    # Autosave Switches
    self.sw_optimize_path = Switch(
      "Optimize Pathing (Sticky Bot)", active_color=CURRENT_THEME.ACCENT_GREEN
    )
    self.sw_optimize_path.setToolTip(
      "If ON: The bot will try to continue moving with the CURRENT player\n"
      "instead of switching to another teammate. Reduces Alt-Tabs."
    )
    # Connect to autosave
    self.sw_optimize_path.toggled.connect(self._autosave_logic)

    self.sw_no_plant = Switch("No Plant", active_color=CURRENT_THEME.ACCENT_ORANGE)
    self.sw_no_plant.setToolTip("Bot will not try to plant and defuse bomb.")
    # Connect to autosave
    self.sw_no_plant.toggled.connect(self._autosave_logic)

    logic_layout.addWidget(self.sw_optimize_path)
    logic_layout.addWidget(self.sw_no_plant)
    logic_layout.addStretch()

    # Add panels to Grid
    grid.addWidget(ai_panel, 0, 0)
    grid.addWidget(logic_panel, 0, 1)

    # Equal width columns
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)

  def _input_style(self):
    return f"""
            background-color: {CURRENT_THEME.INPUT_BACKGROUND};
            color: {CURRENT_THEME.PRIMARY_TEXT};
            border: 1px solid {CURRENT_THEME.BORDER};
            padding: 4px;
            border-radius: 4px;
        """

  def _load_values(self):
    s = self.ctx.settings.user.advanced

    # AI
    idx = self.combo_device.findText(s.inference_device.value.upper())
    if idx >= 0:
      self.combo_device.setCurrentIndex(idx)
    self.spin_threads.setValue(s.inference_threads)

    # Logic (Block signals to prevent autosave triggering during load)
    self.sw_optimize_path.blockSignals(True)
    self.sw_no_plant.blockSignals(True)

    self.sw_optimize_path.setChecked(s.match.fast_paths)
    self.sw_no_plant.setChecked(s.match.no_plant)

    self.sw_optimize_path.blockSignals(False)
    self.sw_no_plant.blockSignals(False)

  def _apply_ai_settings(self):
    """Manually save AI settings and reload model"""
    s = self.ctx.settings.user.advanced

    dev_text = self.combo_device.currentText().lower()
    new_device = InferenceDevice(dev_text)
    new_threads = self.spin_threads.value()

    s.inference_device = new_device
    s.inference_threads = new_threads

    self.ctx.settings.save(self.ctx.settings.user)

    try:
      self.ctx.ai.reload(new_device, new_threads)
      QMessageBox.information(
        self, "Success", f"AI reloaded on {self.ctx.ai.session.get_providers()[0]}"
      )
    except Exception as e:
      QMessageBox.critical(self, "Error", f"Failed to reload model: {e}")

  def _autosave_logic(self, _):
    s = self.ctx.settings.user.advanced

    s.match.fast_paths = self.sw_optimize_path.isChecked()
    s.match.no_plant = self.sw_no_plant.isChecked()

    self.ctx.settings.save(self.ctx.settings.user)

  def _run_benchmark(self):
    self.lbl_bench_result.set("Running...")
    self.btn_bench.setEnabled(False)
    self.btn_reload_ai.setEnabled(False)

    async def task():
      try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, self.ctx.ai.benchmark, 100)

        txt = f"<b>{res['fps']} FPS</b> | {res['latency_ms']}ms | {res['provider']}"
        self.lbl_bench_result.set(txt)
      except Exception as e:
        self.lbl_bench_result.set("Error")
        print(e)
      finally:
        self.btn_bench.setEnabled(True)
        self.btn_reload_ai.setEnabled(True)

    asyncio.create_task(task())
