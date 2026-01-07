import asyncio

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
  QComboBox,
  QGroupBox,
  QHBoxLayout,
  QLabel,
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
    main_layout = QVBoxLayout(self)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    # --- AI Configuration Panel ---
    ai_panel = TitledPanel("AI Inference Settings")
    ai_layout = QVBoxLayout(ai_panel.container)

    # Device Selection
    device_layout = QHBoxLayout()
    device_layout.addWidget(Label("Processing Unit:"))

    self.combo_device = QComboBox()
    self.combo_device.addItems([d.value.upper() for d in InferenceDevice])
    self.combo_device.setStyleSheet(f"""
            QComboBox {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                border: 1px solid {CURRENT_THEME.BORDER};
                padding: 5px;
            }}
        """)
    device_layout.addWidget(self.combo_device)
    ai_layout.addLayout(device_layout)

    # Threads
    threads_layout = QHBoxLayout()
    threads_layout.addWidget(Label("CPU Threads (Intra-op):"))
    self.spin_threads = QSpinBox()
    self.spin_threads.setRange(0, 32)
    self.spin_threads.setStyleSheet(f"""
            QSpinBox {{
                background-color: {CURRENT_THEME.INPUT_BACKGROUND};
                color: {CURRENT_THEME.PRIMARY_TEXT};
                border: 1px solid {CURRENT_THEME.BORDER};
                padding: 5px;
            }}
        """)
    threads_layout.addWidget(self.spin_threads)
    ai_layout.addLayout(threads_layout)

    # Apply Button
    self.btn_apply = Button(
      "Apply & Reload Model",
      on_click=self._apply_ai_settings,
      button_type=ButtonType.PRIMARY,
    )
    ai_layout.addWidget(self.btn_apply)

    main_layout.addWidget(ai_panel)

    # --- Benchmark Panel ---
    bench_panel = TitledPanel("Performance Test")
    bench_layout = QVBoxLayout(bench_panel.container)

    self.lbl_bench_status = Label("Ready to test.", LabelType.SECONDARY)
    self.lbl_bench_result = Label("", LabelType.HEADER)

    self.btn_bench = Button(
      "Run Benchmark", on_click=self._run_benchmark, button_type=ButtonType.DEFAULT
    )

    bench_layout.addWidget(self.lbl_bench_status)
    bench_layout.addWidget(self.lbl_bench_result)
    bench_layout.addWidget(self.btn_bench)

    main_layout.addWidget(bench_panel)
    main_layout.addStretch()

  def _load_values(self):
    settings = self.ctx.settings.user.advanced

    # Set Device
    index = self.combo_device.findText(settings.inference_device.value.upper())
    if index >= 0:
      self.combo_device.setCurrentIndex(index)

    # Set Threads
    self.spin_threads.setValue(settings.inference_threads)

  def _apply_ai_settings(self):
    settings = self.ctx.settings.user.advanced

    selected_text = self.combo_device.currentText().lower()
    new_device = InferenceDevice(selected_text)
    new_threads = self.spin_threads.value()

    settings.inference_device = new_device
    settings.inference_threads = new_threads
    self.ctx.settings.save(self.ctx.settings.user)

    try:
      self.ctx.ai.reload(new_device, new_threads)
      QMessageBox.information(
        self, "Success", f"Model reloaded on {self.ctx.ai.session.get_providers()[0]}"
      )
    except Exception as e:
      QMessageBox.critical(self, "Error", f"Failed to reload model: {e}")

  def _run_benchmark(self):
    self.lbl_bench_status.set("Running benchmark (don't touch)...")
    self.btn_bench.setEnabled(False)
    self.ctx.settings.save(self.ctx.settings.user)  # Save before bench

    async def task():
      try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self.ctx.ai.benchmark, 100)

        green = CURRENT_THEME.ACCENT_GREEN
        orange = CURRENT_THEME.ACCENT_ORANGE
        self.lbl_bench_result.set(
          f"FPS: <span style='color:{green}'>{result['fps']}</span> | "
          f"Latency: <span style='color:{orange}'>{result['latency_ms']} ms</span>"
        )
        self.lbl_bench_status.set("Done.")
      except Exception as e:
        self.lbl_bench_status.set(f"Error: {e}")
      finally:
        self.btn_bench.setEnabled(True)

    asyncio.create_task(task())
