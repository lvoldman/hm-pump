from __future__ import annotations

import sys
from PySide6 import QtCore, QtWidgets


# -----------------------------
# Small SCADA-style status lamp
# -----------------------------
class StatusLamp(QtWidgets.QFrame):
    """
    Simple round indicator.
    States: "off", "ok", "warn", "err"
    """
    def __init__(self, parent=None, size: int = 14):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setObjectName("StatusLamp")
        self.set_state("off")

    def set_state(self, state: str) -> None:
        state = (state or "off").lower()
        if state not in {"off", "ok", "warn", "err"}:
            state = "off"
        self.setProperty("state", state)
        # re-polish so stylesheet applies immediately
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# -----------------------------
# Motor control panel (GUI only)
# -----------------------------
class MotorPanel(QtWidgets.QGroupBox):
    # You will later set running time from your motor code.
    # For GUI-only wiring, we expose a signal to notify others.
    runningTimeTextChanged = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__("Motor", parent)
        self._build_ui()
        self._wire()

    def _build_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # --- Header row: title + status indicator
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        header.addWidget(QtWidgets.QLabel("Status:"))
        self.motor_lamp = StatusLamp(size=14)
        header.addWidget(self.motor_lamp)
        self.motor_status_text = QtWidgets.QLabel("OFF")
        self.motor_status_text.setObjectName("StatusText")
        header.addWidget(self.motor_status_text)
        header.addStretch(1)

        # ---- Move absolute: position + button
        row_abs = QtWidgets.QHBoxLayout()
        row_abs.setSpacing(10)

        self.pos = QtWidgets.QDoubleSpinBox()
        self.pos.setDecimals(4)
        self.pos.setRange(-1e9, 1e9)
        self.pos.setSingleStep(1.0)
        self.pos.setMinimumWidth(180)
        self.pos.setFixedHeight(34)

        self.btn_move_abs = QtWidgets.QPushButton("Move Absolute")
        self.btn_move_abs.setMinimumWidth(150)
        self.btn_move_abs.setFixedHeight(40)

        row_abs.addWidget(QtWidgets.QLabel("Position:"))
        row_abs.addWidget(self.pos)
        row_abs.addSpacing(8)
        row_abs.addWidget(self.btn_move_abs)
        row_abs.addStretch(1)

        # ---- Jog buttons
        row_jog = QtWidgets.QHBoxLayout()
        row_jog.setSpacing(10)

        self.btn_back = QtWidgets.QPushButton("◀ Move Backward")
        self.btn_fwd = QtWidgets.QPushButton("Move Forward ▶")
        for b in (self.btn_back, self.btn_fwd):
            b.setMinimumWidth(170)
            b.setFixedHeight(40)

        row_jog.addWidget(self.btn_back)
        row_jog.addWidget(self.btn_fwd)
        row_jog.addStretch(1)

        # ---- Parameters (accel/vel)
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.accel = QtWidgets.QDoubleSpinBox()
        self.accel.setDecimals(4)
        self.accel.setRange(0.0, 1e9)
        self.accel.setSingleStep(1.0)
        self.accel.setMinimumWidth(180)
        self.accel.setFixedHeight(34)

        self.vel = QtWidgets.QDoubleSpinBox()
        self.vel.setDecimals(4)
        self.vel.setRange(0.0, 1e9)
        self.vel.setSingleStep(1.0)
        self.vel.setMinimumWidth(180)
        self.vel.setFixedHeight(34)

        form.addRow("Acceleration:", self.accel)
        form.addRow("Velocity:", self.vel)

        # ---- Running time (read-only)
        row_time = QtWidgets.QHBoxLayout()
        row_time.setSpacing(10)

        self.running_time = QtWidgets.QLineEdit()
        self.running_time.setReadOnly(True)
        self.running_time.setPlaceholderText("seconds")
        self.running_time.setMinimumWidth(180)
        self.running_time.setFixedHeight(34)

        row_time.addWidget(QtWidgets.QLabel("Running time:"))
        row_time.addWidget(self.running_time)
        row_time.addStretch(1)

        # ---- Timeout enable + timeout value
        row_to = QtWidgets.QHBoxLayout()
        row_to.setSpacing(10)

        self.cb_timeout = QtWidgets.QCheckBox("Enable timeout")

        self.timeout = QtWidgets.QDoubleSpinBox()
        self.timeout.setDecimals(3)
        self.timeout.setRange(0.0, 1e6)
        self.timeout.setSingleStep(0.5)
        self.timeout.setMinimumWidth(180)
        self.timeout.setFixedHeight(34)
        self.timeout.setEnabled(False)

        row_to.addWidget(self.cb_timeout)
        row_to.addSpacing(8)
        row_to.addWidget(QtWidgets.QLabel("Timeout (s):"))
        row_to.addWidget(self.timeout)
        row_to.addStretch(1)

        # ---- Put together
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        main.addLayout(header)
        main.addLayout(row_abs)
        main.addLayout(row_jog)
        main.addLayout(form)
        main.addWidget(line)
        main.addLayout(row_time)
        main.addLayout(row_to)

    def _wire(self):
        self.cb_timeout.toggled.connect(self.timeout.setEnabled)

        # propagate running_time changes to other panels (Weight/Power)
        self.running_time.textChanged.connect(self.runningTimeTextChanged.emit)

        # GUI-only stubs (no hardware)
        self.btn_move_abs.clicked.connect(self._stub_move_abs)
        self.btn_fwd.clicked.connect(self._stub_move_fwd)
        self.btn_back.clicked.connect(self._stub_move_back)

        # initial status
        self.set_motor_status("off", "OFF")

    # ---- Status API (GUI-only for now) ----
    def set_motor_status(self, lamp_state: str, text: str) -> None:
        self.motor_lamp.set_state(lamp_state)
        self.motor_status_text.setText(text)

    # ---- GUI-only stubs ----
    def _stub_move_abs(self):
        self.set_motor_status("ok", "RUNNING")
        self.running_time.setText("1.23")  # demo seconds

    def _stub_move_fwd(self):
        self.set_motor_status("ok", "RUNNING")
        self.running_time.setText("0.80")  # demo seconds

    def _stub_move_back(self):
        self.set_motor_status("ok", "RUNNING")
        self.running_time.setText("0.95")  # demo seconds


# -----------------------------
# Weight & Power (GUI only)
# -----------------------------
class WeightPowerPanel(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Weight / Power", parent)
        self._time_seconds: float | None = None
        self._build_ui()
        self._wire()

    def _build_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # --- Header row: status indicator for scale
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        header.addWidget(QtWidgets.QLabel("Scale status:"))
        self.scale_lamp = StatusLamp(size=14)
        header.addWidget(self.scale_lamp)
        self.scale_status_text = QtWidgets.QLabel("DISCONNECTED")
        self.scale_status_text.setObjectName("StatusText")
        header.addWidget(self.scale_status_text)
        header.addStretch(1)

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        # Weight display: not editable
        self.weight = QtWidgets.QLineEdit()
        self.weight.setReadOnly(True)
        self.weight.setPlaceholderText("Weight from scale")
        self.weight.setMinimumWidth(180)
        self.weight.setFixedHeight(34)

        # Power display
        self.power = QtWidgets.QLineEdit()
        self.power.setReadOnly(True)
        self.power.setMinimumWidth(180)
        self.power.setFixedHeight(34)

        form.addRow("Weight:", self.weight)
        form.addRow("Power (W/T):", self.power)

        row_btn = QtWidgets.QHBoxLayout()
        row_btn.setSpacing(10)

        self.btn_zero = QtWidgets.QPushButton("Zero weight")
        self.btn_zero.setFixedHeight(40)

        self.btn_recalc = QtWidgets.QPushButton("Recalculate")
        self.btn_recalc.setFixedHeight(40)

        row_btn.addWidget(self.btn_zero)
        row_btn.addWidget(self.btn_recalc)
        row_btn.addStretch(1)

        main.addLayout(header)
        main.addLayout(form)
        main.addLayout(row_btn)

        # initial status
        self.set_scale_status("off", "DISCONNECTED")

    def _wire(self):
        self.btn_recalc.clicked.connect(self._recalc)
        self.btn_zero.clicked.connect(self._zero)

        # If weight text changes (you'll set it from your scale code),
        # recalc power automatically.
        self.weight.textChanged.connect(self._recalc)

    # ---- External update API (for later integration) ----
    def set_scale_status(self, lamp_state: str, text: str) -> None:
        self.scale_lamp.set_state(lamp_state)
        self.scale_status_text.setText(text)

    def set_weight_value(self, value: float) -> None:
        # This is the method you’ll call from your scale code.
        self.weight.setText(f"{value:.6g}")

    def set_time_seconds_from_text(self, text: str) -> None:
        # Motor panel provides running time as string
        t = None
        try:
            t = float(text.strip()) if text.strip() else None
        except ValueError:
            t = None
        self._time_seconds = t
        self._recalc()

    # ---- GUI-only helpers ----
    def _zero(self):
        # GUI-only: show zero; later you'll trigger tare on the real scale.
        self.weight.setText("0")

    def _recalc(self):
        # power = weight / time
        # if time missing/<=0 -> blank
        try:
            w_txt = self.weight.text().strip()
            w = float(w_txt) if w_txt else 0.0
        except ValueError:
            self.power.setText("")
            return

        t = self._time_seconds
        if t is None or t <= 0:
            self.power.setText("")
            return

        p = w / t
        self.power.setText(f"{p:.6g}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Panel GUI (PySide6) — Prototype")
        self.resize(1000, 650)
        self._apply_scada_style()
        self._build_ui()

    def _apply_scada_style(self):
        # Unified sizes & SCADA-like clean look
        # (kept conservative; no fancy palette changes)
        self.setStyleSheet("""
            QMainWindow { background: #f4f6f8; }

            QGroupBox {
                font-weight: 600;
                border: 1px solid #c9ced6;
                border-radius: 6px;
                margin-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }

            QLabel { font-size: 12px; }
            QLineEdit, QDoubleSpinBox {
                font-size: 12px;
                padding: 4px 6px;
            }
            QPushButton {
                font-size: 12px;
                font-weight: 600;
            }
            QCheckBox { font-size: 12px; }

            /* Status lamp states */
            #StatusLamp {
                border-radius: 7px;
                border: 1px solid #7a7a7a;
                background: #bdbdbd; /* off default */
            }
            #StatusLamp[state="off"]  { background: #bdbdbd; }
            #StatusLamp[state="ok"]   { background: #2ecc71; }
            #StatusLamp[state="warn"] { background: #f1c40f; }
            #StatusLamp[state="err"]  { background: #e74c3c; }

            QLabel#StatusText {
                font-weight: 700;
            }
        """)

    def _build_ui(self):
        tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(tabs)

        tab = QtWidgets.QWidget()
        tabs.addTab(tab, "Main")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        # Layout inside scroll
        grid = QtWidgets.QGridLayout(content)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.motor_panel = MotorPanel()
        self.wp_panel = WeightPowerPanel()

        # Wire motor running time -> power panel time
        self.motor_panel.runningTimeTextChanged.connect(self.wp_panel.set_time_seconds_from_text)

        grid.addWidget(self.motor_panel, 0, 0)
        grid.addWidget(self.wp_panel, 0, 1)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)

        # Put scroll into the tab
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self.statusBar().showMessage("Ready")


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
