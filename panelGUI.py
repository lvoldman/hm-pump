# panelGUI.py
# Pure GUI (PySide6).
# before running - conda activate hm (or your env with PySide6)
# then: python panelGUI.py

from __future__ import annotations

import sys
from PySide6 import QtCore, QtGui, QtWidgets

class MotorPanel(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Motor", parent)
        self._build_ui()
        self._wire()

    def _build_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # ---- Move absolute: position + button
        row_abs = QtWidgets.QHBoxLayout()
        row_abs.setSpacing(10)

        self.pos = QtWidgets.QDoubleSpinBox()
        self.pos.setDecimals(4)
        self.pos.setRange(-1e9, 1e9)
        self.pos.setSingleStep(1.0)
        self.pos.setMinimumWidth(180)

        self.btn_move_abs = QtWidgets.QPushButton("Move Absolute")
        self.btn_move_abs.setMinimumHeight(36)
        self.btn_move_abs.setMinimumWidth(150)

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
            b.setMinimumHeight(40)
            b.setMinimumWidth(170)

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

        self.vel = QtWidgets.QDoubleSpinBox()
        self.vel.setDecimals(4)
        self.vel.setRange(0.0, 1e9)
        self.vel.setSingleStep(1.0)
        self.vel.setMinimumWidth(180)

        form.addRow("Acceleration:", self.accel)
        form.addRow("Velocity:", self.vel)

        # ---- Running time
        row_time = QtWidgets.QHBoxLayout()
        row_time.setSpacing(10)

        self.running_time = QtWidgets.QLineEdit()
        self.running_time.setReadOnly(True)
        self.running_time.setPlaceholderText("seconds")
        self.running_time.setMinimumWidth(180)

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

        main.addLayout(row_abs)
        main.addLayout(row_jog)
        main.addLayout(form)
        main.addWidget(line)
        main.addLayout(row_time)
        main.addLayout(row_to)

    def _wire(self):
        self.cb_timeout.toggled.connect(self.timeout.setEnabled)

        # GUI-only stubs (no hardware)
        self.btn_move_abs.clicked.connect(lambda: self.running_time.setText("(move abs requested)"))
        self.btn_fwd.clicked.connect(lambda: self.running_time.setText("(move forward requested)"))
        self.btn_back.clicked.connect(lambda: self.running_time.setText("(move backward requested)"))


class WeightPowerPanel(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Weight / Power", parent)
        self._build_ui()
        self._wire()

    def _build_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.weight = QtWidgets.QDoubleSpinBox()
        self.weight.setDecimals(4)
        self.weight.setRange(-1e9, 1e9)
        self.weight.setSingleStep(0.1)
        self.weight.setMinimumWidth(180)

        self.time = QtWidgets.QDoubleSpinBox()
        self.time.setDecimals(4)
        self.time.setRange(0.0, 1e9)
        self.time.setSingleStep(0.1)
        self.time.setMinimumWidth(180)

        self.power = QtWidgets.QLineEdit()
        self.power.setReadOnly(True)
        self.power.setMinimumWidth(180)

        form.addRow("Weight:", self.weight)
        form.addRow("Time (s):", self.time)
        form.addRow("Power (W/T):", self.power)

        row_btn = QtWidgets.QHBoxLayout()
        row_btn.setSpacing(10)

        self.btn_zero = QtWidgets.QPushButton("Zero weight")
        self.btn_zero.setMinimumHeight(36)

        self.btn_recalc = QtWidgets.QPushButton("Recalculate")
        self.btn_recalc.setMinimumHeight(36)

        row_btn.addWidget(self.btn_zero)
        row_btn.addWidget(self.btn_recalc)
        row_btn.addStretch(1)

        main.addLayout(form)
        main.addLayout(row_btn)

    def _wire(self):
        self.weight.valueChanged.connect(self._recalc)
        self.time.valueChanged.connect(self._recalc)
        self.btn_recalc.clicked.connect(self._recalc)
        self.btn_zero.clicked.connect(self._zero)

        self._recalc()

    def _zero(self):
        self.weight.setValue(0.0)

    def _recalc(self):
        t = self.time.value()
        if t <= 0:
            self.power.setText("")
            return
        p = self.weight.value() / t
        self.power.setText(f"{p:.6g}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Panel GUI (PySide6) — Prototype")
        self.resize(1000, 650)
        self._build_ui()

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
