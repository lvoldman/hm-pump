# panelGUI.py
# Pure GUI (PySide6).
# before running - conda activate hm (or your env with PySide6)
# then: python panelGUI.py

from __future__ import annotations

import sys
from PySide6 import QtCore, QtGui, QtWidgets


class MotorPanel(QtWidgets.QGroupBox):
    """
    Motor control panel (GUI only).
    Contains:
      - position input + Move Absolute button
      - Move Forward / Move Backward buttons
      - running time (read-only field)
      - Enable timeout checkbox + timeout input
      - acceleration + velocity inputs
    """
    def __init__(self, parent=None):
        super().__init__("Motor #1", parent)
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        # Top-level layout inside the group box
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # ---- Row 1: Position + Move Absolute ----
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(8)

        self.position_edit = QtWidgets.QLineEdit()
        self.position_edit.setPlaceholderText("Position (e.g. 12.34)")
        self.position_edit.setClearButtonEnabled(True)
        self.position_edit.setMaximumWidth(220)
        self.position_edit.setValidator(QtGui.QDoubleValidator(bottom=-1e12, top=1e12, decimals=6))

        self.move_abs_btn = QtWidgets.QPushButton("Move Absolute")
        self.move_abs_btn.setMinimumWidth(140)

        row1.addWidget(QtWidgets.QLabel("Position:"))
        row1.addWidget(self.position_edit)
        row1.addSpacing(8)
        row1.addWidget(self.move_abs_btn)
        row1.addStretch(1)

        # ---- Row 2: Move fwd/back ----
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(8)

        self.move_fwd_btn = QtWidgets.QPushButton("Move Forward")
        self.move_back_btn = QtWidgets.QPushButton("Move Backward")
        self.move_fwd_btn.setMinimumWidth(140)
        self.move_back_btn.setMinimumWidth(140)

        row2.addWidget(self.move_back_btn)
        row2.addWidget(self.move_fwd_btn)
        row2.addStretch(1)

        # ---- Row 3: Running time ----
        row3 = QtWidgets.QHBoxLayout()
        row3.setSpacing(8)

        self.running_time_edit = QtWidgets.QLineEdit()
        self.running_time_edit.setReadOnly(True)
        self.running_time_edit.setPlaceholderText("seconds")
        self.running_time_edit.setMaximumWidth(220)

        row3.addWidget(QtWidgets.QLabel("Running time:"))
        row3.addWidget(self.running_time_edit)
        row3.addStretch(1)

        # ---- Row 4: Timeout enable + timeout value ----
        row4 = QtWidgets.QHBoxLayout()
        row4.setSpacing(8)

        self.enable_timeout_cb = QtWidgets.QCheckBox("Enable timeout")
        self.timeout_edit = QtWidgets.QLineEdit()
        self.timeout_edit.setPlaceholderText("Timeout (s)")
        self.timeout_edit.setClearButtonEnabled(True)
        self.timeout_edit.setMaximumWidth(220)
        self.timeout_edit.setValidator(QtGui.QDoubleValidator(bottom=0.0, top=1e9, decimals=3))
        self.timeout_edit.setEnabled(False)

        row4.addWidget(self.enable_timeout_cb)
        row4.addSpacing(8)
        row4.addWidget(QtWidgets.QLabel("Timeout:"))
        row4.addWidget(self.timeout_edit)
        row4.addStretch(1)

        # ---- Row 5: Acceleration + Velocity ----
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self.accel_edit = QtWidgets.QLineEdit()
        self.accel_edit.setPlaceholderText("Acceleration")
        self.accel_edit.setClearButtonEnabled(True)
        self.accel_edit.setMaximumWidth(220)
        self.accel_edit.setValidator(QtGui.QDoubleValidator(bottom=0.0, top=1e12, decimals=6))

        self.vel_edit = QtWidgets.QLineEdit()
        self.vel_edit.setPlaceholderText("Velocity")
        self.vel_edit.setClearButtonEnabled(True)
        self.vel_edit.setMaximumWidth(220)
        self.vel_edit.setValidator(QtGui.QDoubleValidator(bottom=0.0, top=1e12, decimals=6))

        form.addRow("Acceleration:", self.accel_edit)
        form.addRow("Velocity:", self.vel_edit)

        # Optional: separator line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        # Assemble
        main.addLayout(row1)
        main.addLayout(row2)
        main.addWidget(line)
        main.addLayout(row3)
        main.addLayout(row4)
        main.addLayout(form)
        main.addStretch(1)

    def _wire_signals(self) -> None:
        self.enable_timeout_cb.toggled.connect(self.timeout_edit.setEnabled)

        # GUI-only stubs: connect buttons to placeholder handlers
        self.move_abs_btn.clicked.connect(self._on_move_absolute_clicked)
        self.move_fwd_btn.clicked.connect(self._on_move_forward_clicked)
        self.move_back_btn.clicked.connect(self._on_move_backward_clicked)

        # Optional: Enter in position triggers move absolute
        self.position_edit.returnPressed.connect(self._on_move_absolute_clicked)

    # --- GUI-only placeholders (no hardware logic) ---
    def _on_move_absolute_clicked(self) -> None:
        pos = self.position_edit.text().strip()
        # Placeholder: show intent in running time field (or status bar later)
        if pos:
            self.running_time_edit.setText(f"(move abs requested to {pos})")
        else:
            self.running_time_edit.setText("(move abs requested)")

    def _on_move_forward_clicked(self) -> None:
        self.running_time_edit.setText("(move forward requested)")

    def _on_move_backward_clicked(self) -> None:
        self.running_time_edit.setText("(move backward requested)")


class WeightPowerPanel(QtWidgets.QGroupBox):
    """
    Weight & Power panel (GUI only).
      - weight display
      - time display (can reuse the "running time" concept, but here separate)
      - power display = weight/time (we'll compute in GUI just for display demo)
    """
    def __init__(self, parent=None):
        super().__init__("Weight & Power", parent)
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # Displays
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.weight_edit = QtWidgets.QLineEdit()
        self.weight_edit.setReadOnly(False)  # Often weight comes from sensor; for GUI demo allow input
        self.weight_edit.setPlaceholderText("Weight")
        self.weight_edit.setMaximumWidth(220)
        self.weight_edit.setValidator(QtGui.QDoubleValidator(bottom=-1e12, top=1e12, decimals=6))
        self.weight_edit.setClearButtonEnabled(True)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setReadOnly(False)  # For GUI demo allow input
        self.time_edit.setPlaceholderText("Time (s)")
        self.time_edit.setMaximumWidth(220)
        self.time_edit.setValidator(QtGui.QDoubleValidator(bottom=0.0, top=1e12, decimals=6))
        self.time_edit.setClearButtonEnabled(True)

        self.power_edit = QtWidgets.QLineEdit()
        self.power_edit.setReadOnly(True)
        self.power_edit.setPlaceholderText("Power = Weight / Time")
        self.power_edit.setMaximumWidth(220)

        grid.addWidget(QtWidgets.QLabel("Weight:"), 0, 0)
        grid.addWidget(self.weight_edit, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Time:"), 1, 0)
        grid.addWidget(self.time_edit, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Power:"), 2, 0)
        grid.addWidget(self.power_edit, 2, 1)

        # Buttons (optional)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        self.zero_weight_btn = QtWidgets.QPushButton("Zero Weight")
        self.recalc_btn = QtWidgets.QPushButton("Recalculate Power")

        btn_row.addWidget(self.zero_weight_btn)
        btn_row.addWidget(self.recalc_btn)
        btn_row.addStretch(1)

        main.addLayout(grid)
        main.addLayout(btn_row)
        main.addStretch(1)

    def _wire_signals(self) -> None:
        # Auto-recompute on edits (GUI demo)
        self.weight_edit.textChanged.connect(self._recompute_power)
        self.time_edit.textChanged.connect(self._recompute_power)

        self.zero_weight_btn.clicked.connect(self._on_zero_weight)
        self.recalc_btn.clicked.connect(self._recompute_power)

    def _on_zero_weight(self) -> None:
        self.weight_edit.setText("0")
        self._recompute_power()

    def _recompute_power(self) -> None:
        # Pure UI calc for display. Replace later with real computed tag if needed.
        w_txt = self.weight_edit.text().strip()
        t_txt = self.time_edit.text().strip()

        try:
            w = float(w_txt) if w_txt else 0.0
            t = float(t_txt) if t_txt else 0.0
        except ValueError:
            self.power_edit.setText("")
            return

        if t <= 0.0:
            self.power_edit.setText("")
            return

        p = w / t
        self.power_edit.setText(f"{p:.6g}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCADA GUI (PySide6) — Prototype")
        self.resize(980, 600)

        self._build_ui()
        self._build_menu()

    def _build_ui(self) -> None:
        tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(tabs)

        # Single tab as requested
        tab1 = QtWidgets.QWidget()
        tabs.addTab(tab1, "Main")

        # Scroll area so you can add lots of controls later without re-layout headaches
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        root = QtWidgets.QWidget()
        scroll.setWidget(root)

        # Layout inside scroll
        # Two panels side-by-side. On smaller widths they'll still be visible; you can adapt later.
        h = QtWidgets.QHBoxLayout(root)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(12)

        self.motor_panel = MotorPanel()
        self.weight_panel = WeightPowerPanel()

        self.motor_panel.setMinimumWidth(450)
        self.weight_panel.setMinimumWidth(350)

        h.addWidget(self.motor_panel, 2)
        h.addWidget(self.weight_panel, 1)
        h.addStretch(1)

        # Place scroll in tab
        tab_layout = QtWidgets.QVBoxLayout(tab1)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        # Status bar (useful later for events)
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        act_exit = QtGui.QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        view_menu = menubar.addMenu("View")
        act_reset = QtGui.QAction("Reset Fields (GUI)", self)
        act_reset.triggered.connect(self._reset_fields)
        view_menu.addAction(act_reset)

        help_menu = menubar.addMenu("Help")
        act_about = QtGui.QAction("About", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    def _reset_fields(self) -> None:
        # Purely GUI reset for convenience
        for w in [
            self.motor_panel.position_edit,
            self.motor_panel.running_time_edit,
            self.motor_panel.timeout_edit,
            self.motor_panel.accel_edit,
            self.motor_panel.vel_edit,
            self.weight_panel.weight_edit,
            self.weight_panel.time_edit,
            self.weight_panel.power_edit,
        ]:
            if isinstance(w, QtWidgets.QLineEdit) and not w.isReadOnly():
                w.clear()
            elif isinstance(w, QtWidgets.QLineEdit) and w.isReadOnly():
                w.clear()

        self.motor_panel.enable_timeout_cb.setChecked(False)
        self.statusBar().showMessage("Fields reset", 2000)

    def _about(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "About",
            "Prototype SCADA GUI built with PySide6.\n"
            "This version contains GUI only (no hardware control)."
        )


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("SCADA GUI Prototype")

    # Optional: nicer default font scaling on Windows
    app.setStyle("Fusion")

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
