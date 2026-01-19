from __future__ import annotations

import sys

from PySide6 import QtCore, QtWidgets, QtGui
from servo_motor import servoMotor, servoParameters
from WLCscale  import serialScale



import time
from enum import Enum

# -----------------------------
# Worker infrastructure (Qt threads)
# -----------------------------
class MotorState(Enum):
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class MotorWorker(QtCore.QObject):
    connectedChanged = QtCore.Signal(bool)
    stateChanged = QtCore.Signal(str)              # MotorState value string
    telemetryChanged = QtCore.Signal(dict)
    error = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self._motor: servoMotor | None = None
        self._sn: str | None = None
        self._state: MotorState = MotorState.DISCONNECTED
        self._elapsed_accum: float = 0.0
        self._segment_start: float | None = None
        self._elapsed_timer = QtCore.QTimer()
        self._elapsed_timer.setInterval(100)  # ms
        self._elapsed_timer.timeout.connect(self._emit_elapsed)
        self._last_cmd: tuple[str, tuple, dict] | None = None  # (name, args, kwargs)

    @QtCore.Slot(str)
    def connect_motor(self, sn: str) -> None:
        try:
            if not sn or "not selected" in sn:
                self.disconnect_motor()
                return
            # NOTE: servoMotor currently has no real connect-by-SN; we keep SN for future integration.
            self._motor = servoMotor()
            self._sn = sn
            self._set_state(MotorState.IDLE)
            self.connectedChanged.emit(True)
        except Exception as ex:
            self._motor = None
            self._sn = None
            self._set_state(MotorState.ERROR)
            self.connectedChanged.emit(False)
            self.error.emit(f"Motor connect failed: {ex}")

    @QtCore.Slot()
    def disconnect_motor(self) -> None:
        try:
            self._stop_elapsed()
            self._motor = None
            self._sn = None
            self.connectedChanged.emit(False)
            self._set_state(MotorState.DISCONNECTED)
        except Exception as ex:
            self.error.emit(f"Motor disconnect failed: {ex}")

    @QtCore.Slot(dict)
    def move_abs(self, payload: dict) -> None:
        # _unused kept for signature stability
        if not self._motor:
            self.error.emit("Motor not connected")
            return
        try:
            position = float(payload.get('position', 0.0))

            velocity = float(payload.get('velocity', 0.0))
            acceleration = float(payload.get('acceleration', 0.0))
            timeout_enabled = bool(payload.get('timeout_enabled', False))
            timeout = float(payload.get('timeout', 0.0))

            parms = servoParameters(
                velocity=velocity,
                acceleration=acceleration,
                timeout=(timeout if timeout_enabled else None),
            )
            self._last_cmd = ("move_abs", (position, velocity, acceleration, timeout, timeout_enabled), {})
            ok = self._motor.go2pos(position, parms)
            if ok is False:
                self._set_state(MotorState.ERROR)
                self.error.emit("Motor move_abs command failed")
                return
            self._start_elapsed(reset=True)
            self._set_state(MotorState.RUNNING)
            self._emit_telemetry({"cmd": "move_abs", "pos": position, "vel": velocity, "accel": acceleration})
            # Wait for completion in this worker thread (blocking OK here)
            self._wait_for_completion()
        except Exception as ex:
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor move_abs exception: {ex}")

    @QtCore.Slot(int, dict)
    def jog(self, direction: int, payload: dict) -> None:
        if not self._motor:
            self.error.emit("Motor not connected")
            return
        try:
            velocity = float(payload.get('velocity', 0.0))
            acceleration = float(payload.get('acceleration', 0.0))
            timeout_enabled = bool(payload.get('timeout_enabled', False))
            timeout = float(payload.get('timeout', 0.0))

            parms = servoParameters(
                velocity=velocity,
                acceleration=acceleration,
                timeout=(timeout if timeout_enabled else None),
            )
            self._last_cmd = ("jog", (direction, velocity, acceleration, timeout, timeout_enabled), {})
            if direction >= 0:
                ok = self._motor.forward(parms)
                cmd = "forward"
            else:
                ok = self._motor.backward(parms)
                cmd = "backward"
            if ok is False:
                self._set_state(MotorState.ERROR)
                self.error.emit(f"Motor {cmd} command failed")
                return
            self._start_elapsed(reset=True)
            self._set_state(MotorState.RUNNING)
            self._emit_telemetry({"cmd": cmd, "vel": velocity, "accel": acceleration})
            self._wait_for_completion()
        except Exception as ex:
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor jog exception: {ex}")

    @QtCore.Slot()
    def stop(self) -> None:
        if not self._motor:
            return
        try:
            self._motor.stop()
            self._stop_elapsed()
            self._set_state(MotorState.IDLE)
            self._emit_telemetry({"cmd": "stop"})
        except Exception as ex:
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor stop exception: {ex}")

    @QtCore.Slot()
    def pause(self) -> None:
        # For now, we implement pause as stop + state=PAUSED.
        # Later, if hardware supports true pause, this method will change.
        if not self._motor:
            return
        try:
            self._motor.stop()
            self._stop_elapsed()
            self._set_state(MotorState.PAUSED)
            self._emit_telemetry({"cmd": "pause"})
        except Exception as ex:
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor pause exception: {ex}")

    @QtCore.Slot()
    def resume(self) -> None:
        # Best-effort resume: re-issue last command if available.
        if not self._motor:
            return
        if not self._last_cmd:
            self.error.emit("Nothing to resume")
            return
        name, args, kwargs = self._last_cmd
        try:
            if name == "move_abs":
                position, velocity, acceleration, timeout, timeout_enabled = args
                self.move_abs({"position": position, "velocity": velocity, "acceleration": acceleration, "timeout": timeout, "timeout_enabled": timeout_enabled})
                return
            if name == "jog":
                direction, velocity, acceleration, timeout, timeout_enabled = args
                self.jog(direction, {"velocity": velocity, "acceleration": acceleration, "timeout": timeout, "timeout_enabled": timeout_enabled})
                return
        except Exception as ex:
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor resume exception: {ex}")

    # ---- internal helpers ----
    def _wait_for_completion(self) -> None:
        # If servoMotor uses its own watchdog thread and posts status to devNotificationQ,
        # we can wait here. This blocks only the worker thread.
        try:
            if not self._motor:
                return
            status = self._motor.devNotificationQ.get()  # blocks
            self._stop_elapsed()
            if status:
                self._set_state(MotorState.IDLE)
            else:
                self._set_state(MotorState.ERROR)
                self.error.emit("Motor operation failed / timed out")
        except Exception as ex:
            self._stop_elapsed()
            self._set_state(MotorState.ERROR)
            self.error.emit(f"Motor completion wait failed: {ex}")

    def _set_state(self, st: MotorState) -> None:
        self._state = st
        self.stateChanged.emit(st.value)

    def _emit_telemetry(self, d: dict) -> None:
        d2 = dict(d)
        d2["motor_sn"] = self._sn
        d2["state"] = self._state.value
        self.telemetryChanged.emit(d2)

    def _start_elapsed(self, reset: bool) -> None:
        if reset:
            self._elapsed_accum = 0.0
        self._segment_start = time.time()
        if not self._elapsed_timer.isActive():
            self._elapsed_timer.start()
        self._emit_elapsed()

    def _stop_elapsed(self) -> None:
        if self._segment_start is not None:
            self._elapsed_accum += time.time() - self._segment_start
            self._segment_start = None
        if self._elapsed_timer.isActive():
            self._elapsed_timer.stop()
        self._emit_elapsed()

    def _emit_elapsed(self) -> None:
        elapsed = self._elapsed_accum
        if self._segment_start is not None:
            elapsed += time.time() - self._segment_start
        self.telemetryChanged.emit({"elapsed_s": elapsed, "motor_sn": self._sn, "state": self._state.value})


class ScaleWorker(QtCore.QObject):
    connectedChanged = QtCore.Signal(bool)
    telemetryChanged = QtCore.Signal(dict)
    error = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self._scale: serialScale | None = None
        self._port: str | None = None
        self._poll_interval: float = 0.5
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._poll_once)

    @QtCore.Slot(str)
    def connect_scale(self, port: str) -> None:
        try:
            if not port or "not selected" in port:
                self.disconnect_scale()
                return
            self._port = port
            self._scale = serialScale(port, poll_interval=self._poll_interval)
            ok = self._scale.connect()
            self.connectedChanged.emit(bool(ok))
            if ok:
                self._restart_timer()
                self.telemetryChanged.emit({"scale_port": self._port, "connected": True})
            else:
                self.telemetryChanged.emit({"scale_port": self._port, "connected": False})
        except Exception as ex:
            self.connectedChanged.emit(False)
            self.error.emit(f"Scale connect failed: {ex}")

    @QtCore.Slot()
    def disconnect_scale(self) -> None:
        try:
            self._timer.stop()
            if self._scale:
                self._scale.disconnect()
            self._scale = None
            self._port = None
            self.connectedChanged.emit(False)
            self.telemetryChanged.emit({"connected": False})
        except Exception as ex:
            self.error.emit(f"Scale disconnect failed: {ex}")

    @QtCore.Slot(float)
    def set_poll_interval(self, seconds: float) -> None:
        self._poll_interval = max(0.05, float(seconds))
        self._restart_timer()

    @QtCore.Slot()
    def zero(self) -> None:
        # GUI-only placeholder; tare command may exist later
        self.telemetryChanged.emit({"cmd": "zero", "scale_port": self._port})

    def _restart_timer(self) -> None:
        if self._scale and self._scale.connection and self._scale.connection.is_open:
            self._timer.start(int(self._poll_interval * 1000))
        else:
            self._timer.stop()

    def _poll_once(self) -> None:
        try:
            if not self._scale:
                return
            w = self._scale.read_weight()
            self.telemetryChanged.emit({"weight": w, "scale_port": self._port})
        except Exception as ex:
            self.error.emit(f"Scale poll error: {ex}")
# -----------------------------
# Small SCADA-style status lamp
# -----------------------------
class StatusLamp(QtWidgets.QFrame):
# Simple round indicator.
# States: "off", "ok", "warn", "err"
    def __init__(self, parent=None, size: int = 14):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setObjectName("StatusLamp")  # for stylesheet
        self.set_state("off")              # default state

    def set_state(self, state: str) -> None:
        state = (state or "off").lower()                    # if none given then "off"
        if state not in {"off", "ok", "warn", "err"}:
            state = "off"
        self.setProperty("state", state)                    # set dynamic property for stylesheet
        # re-polish so stylesheet applies immediately
        self.style().unpolish(self)                         # remove old style
        self.style().polish(self)                           # apply new style
        self.update()                                       # trigger repaint 


# -----------------------------
# Motor control panel (GUI only)
# -----------------------------
class MotorPanel(QtWidgets.QGroupBox):
    # You will later set running time from your motor code.
    # For GUI-only wiring, we expose a signal to notify others.
    runningTimeTextChanged = QtCore.Signal(str)

    motorSelected = QtCore.Signal(str)
    moveAbsRequested = QtCore.Signal(dict)
    jogRequested = QtCore.Signal(int, dict)
    stopRequested = QtCore.Signal()
    pauseToggled = QtCore.Signal(bool)
    def __init__(self, parent=None):
        super().__init__("Motor", parent)
        self._build_ui()
        self._init_workers()
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

        # Motor selector (SN)
        header.addSpacing(16)
        header.addWidget(QtWidgets.QLabel("Motor:"))

        self.motor_select = QtWidgets.QComboBox()
        self.motor_select.setMinimumWidth(220)
        self.motor_select.setFixedHeight(34)
        self.motor_select.addItem("— not selected —")
        header.addWidget(self.motor_select)


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
        self.btn_move_abs.setProperty("role", "primary")

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

        self.btn_pause = QtWidgets.QPushButton("Pause")
        self.btn_pause.setProperty("role", "secondary")
        self.btn_stop = QtWidgets.QPushButton("■ STOP")

        self.btn_fwd.setProperty("role", "primary")
        self.btn_back.setProperty("role", "primary")
        self.btn_stop.setProperty("role", "primary")

        
        self.btn_stop.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; }")
        
        for b in (self.btn_back, self.btn_fwd, self.btn_stop):
            b.setMinimumWidth(170)
            b.setFixedHeight(40)

        row_jog.addWidget(self.btn_back)
        row_jog.addWidget(self.btn_fwd)
        row_jog.addWidget(self.btn_pause)
        row_jog.addWidget(self.btn_stop)
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


        self.btn_reset_time = QtWidgets.QPushButton("Reset")
        self.btn_reset_time.setFixedHeight(34)
        self.btn_reset_time.setMinimumWidth(80)
        self.btn_reset_time.setProperty("role", "neutral")

        row_time.addWidget(self.btn_reset_time)
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
        self.btn_move_abs.clicked.connect(self._on_move_abs_clicked)
        self.btn_fwd.clicked.connect(lambda: self._on_jog_clicked(+1))
        self.btn_back.clicked.connect(lambda: self._on_jog_clicked(-1))
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.btn_stop.clicked.connect(self._stub_move_stop)
        self.btn_reset_time.clicked.connect(self._reset_running_time)
        self.motor_select.currentTextChanged.connect(self._on_motor_selected)
        
        # initial status
        self.set_motor_status("off", "OFF")

        # print(f'Starting watchdog thread for I/O control ')

    
    # reset running time display
    def _reset_running_time(self):
        # GUI-only reset; real motor code will override this later
        self.running_time.setText("")
        self.set_motor_status("off", "IDLE")
    
    # ---- Status API (GUI-only for now) ----
    def set_motor_status(self, lamp_state: str, text: str) -> None:
        self.motor_lamp.set_state(lamp_state)
        self.motor_status_text.setText(text)
        print(f"Motor status set to: {lamp_state} / {text}")
    def _on_move_abs_clicked(self) -> None:
        payload = {
            "position": float(self.pos.value()),
            "velocity": float(self.vel.value()),
            "acceleration": float(self.accel.value()),
            "timeout_enabled": bool(self.cb_timeout.isChecked()),
            "timeout": float(self.timeout.value()),
        }
        self.moveAbsRequested.emit(payload)

    def _on_jog_clicked(self, direction: int) -> None:
        payload = {
            "velocity": float(self.vel.value()),
            "acceleration": float(self.accel.value()),
            "timeout_enabled": bool(self.cb_timeout.isChecked()),
            "timeout": float(self.timeout.value()),
        }
        self.jogRequested.emit(direction, payload)

    def _on_pause_clicked(self) -> None:
        # toggle Pause <-> Resume
        want_pause = (self.btn_pause.text().strip().lower() == "pause")
        if want_pause:
            self.btn_pause.setText("Resume")
            self.pauseToggled.emit(True)
        else:
            self.btn_pause.setText("Pause")
            self.pauseToggled.emit(False)


# -----------------------------
# Weight & Power (GUI only)
# -----------------------------
class WeightPowerPanel(QtWidgets.QGroupBox):
    scaleSelected = QtCore.Signal(str)
    pollIntervalChanged = QtCore.Signal(float)
    zeroRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__("Weight / Power", parent)
        self._time_seconds: float | None = None
        self._build_ui()
        self._init_workers()
        self._wire()

    def _build_ui(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.poll_interval = QtWidgets.QDoubleSpinBox()
        self.poll_interval.setDecimals(2)
        self.poll_interval.setRange(0.10, 3600.0)
        self.poll_interval.setSingleStep(0.10)
        self.poll_interval.setValue(1.0)  # default: every 1 second
        self.poll_interval.setFixedHeight(34)
        self.poll_interval.setMinimumWidth(140)
        self.poll_interval.setToolTip("Interval between weight readings from the scale (seconds).")

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Poll interval (s):"))
        controls.addWidget(self.poll_interval)
        controls.addStretch(1)

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


        # Scale selector (serial port)
        header.addSpacing(16)
        header.addWidget(QtWidgets.QLabel("Port:"))

        self.scale_select = QtWidgets.QComboBox()
        self.scale_select.setMinimumWidth(220)
        self.scale_select.setFixedHeight(34)
        self.scale_select.addItem("— not selected —")
        header.addWidget(self.scale_select)

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

        self.btn_zero.setProperty("role", "neutral")
        self.btn_recalc.setProperty("role", "secondary")

        row_btn.addWidget(self.btn_zero)
        row_btn.addWidget(self.btn_recalc)
        row_btn.addStretch(1)

        main.addLayout(header)
        main.addLayout(form)
        main.addLayout(controls)
        main.addLayout(row_btn)

        # initial status
        self.set_scale_status("off", "DISCONNECTED")

    def _wire(self):
        self.btn_recalc.clicked.connect(self._recalc)
        self.btn_zero.clicked.connect(lambda: self.zeroRequested.emit())
        self.btn_zero.clicked.connect(self._zero)

        # If weight text changes (you'll set it from your scale code),
        # recalc power automatically.
        self.weight.textChanged.connect(self._recalc)
        self.resolution.valueChanged.connect(lambda v: self.pollIntervalChanged.emit(float(v)))

        self.scale_select.currentTextChanged.connect(self._on_scale_selected)


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

    def set_scale_list(self, ports: list[str]) -> None:
        """Call this later with serialScale.listScales()->list[str]."""
        cur = self.scale_select.currentText()
        self.scale_select.blockSignals(True)
        self.scale_select.clear()
        self.scale_select.addItem("— not selected —")
        for p in ports:
            self.scale_select.addItem(p)
        idx = self.scale_select.findText(cur)
        self.scale_select.setCurrentIndex(idx if idx >= 0 else 0)
        self.scale_select.blockSignals(False)

    def _on_scale_selected(self, port: str) -> None:
        self.scaleSelected.emit(port)
        # GUI-only for now
        if port and "not selected" not in port:
            self.set_scale_status("warn", f"SELECTED {port}")
        else:
            self.set_scale_status("off", "DISCONNECTED")


"""
GUI-only log tab:
    - resolution field (seconds)
    - read-only text log (timestamp, velocity, weight, power, etc.)
"""
class LogPanel(QtWidgets.QWidget):

    resolutionChanged = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._init_workers()
        self._wire()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(10)

        self.resolution = QtWidgets.QDoubleSpinBox()
        self.resolution.setDecimals(2)
        self.resolution.setRange(0.10, 3600.0)
        self.resolution.setSingleStep(0.10)
        self.resolution.setValue(1.0)  # default: every 1 second
        self.resolution.setFixedHeight(34)
        self.resolution.setMinimumWidth(140)

        controls.addWidget(QtWidgets.QLabel("Poll interval (s):"))
        controls.addWidget(self.resolution)
        controls.addStretch(1)

        

        #-------- 
        self.max_lines = QtWidgets.QSpinBox()
        self.max_lines.setRange(100, 1_000_000)
        self.max_lines.setValue(5000)  # default
        self.max_lines.setFixedHeight(34)
        self.max_lines.setMinimumWidth(120)

        self.btn_clear = QtWidgets.QPushButton("Clear")
        self.btn_clear.setFixedHeight(34)
        self.btn_clear.setProperty("role", "neutral")  # role-based QSS

        controls.addSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Max size (lines):"))
        controls.addWidget(self.max_lines)
        controls.addSpacing(10)
        controls.addWidget(self.btn_clear)

        #-------- Log output area -------

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(5000)  # default
        self.log.setPlaceholderText("Log output...")
        self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)

        root.addLayout(controls)
        root.addWidget(self.log, 1)

    def _wire(self):
        self.resolution.valueChanged.connect(lambda v: self.resolutionChanged.emit(float(v)))
        self.btn_clear.clicked.connect(self.log.clear)
        self.max_lines.valueChanged.connect(
            lambda v: self.log.document().setMaximumBlockCount(int(v))
        )

    def append_line(self, line: str) -> None:
        self.log.appendPlainText(line)

        # keep view pinned to bottom
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Panel GUI (PySide6) — Prototype")
        self.resize(1000, 650)
        self._apply_scada_style()
        self._build_ui()
        self._init_workers()

#  --- GUI-only periodic logging ---
        self._log_timer = QtCore.QTimer(self)
        self._log_timer.timeout.connect(self._append_log_sample)
        self._log_timer.start(int(self.log_tab.resolution.value() * 1000))

        self.log_tab.resolutionChanged.connect(self._on_log_resolution_changed)

        self.motor_panel.set_motor_list(servoMotor.listMotors())
        self.wp_panel.set_scale_list(serialScale.listScales())

    def _on_log_resolution_changed(self, seconds: float) -> None:
        ms = max(100, int(seconds * 1000))
        self._log_timer.setInterval(ms)

    def _append_log_sample(self) -> None:
        # Log only when motor is running
        if getattr(self, '_motor_state', 'OFF') != MotorState.RUNNING.value:
            return
        # Timestamp
        ts = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")

        # Values from existing GUI (GUI-only; later you will feed these from hardware)
        vel = self.motor_panel.vel.value()
        accel = self.motor_panel.accel.value()
        pos = self.motor_panel.pos.value()

        weight_txt = self.wp_panel.weight.text().strip()
        power_txt = self.wp_panel.power.text().strip()

        motor_status = self.motor_panel.motor_status_text.text().strip()
        scale_status = self.wp_panel.scale_status_text.text().strip()

        # Compose CSV-like line
        line = (
            f"{ts}, "
            f"vel={vel:.4g}, accel={accel:.4g}, pos={pos:.4g}, "
            f"weight={weight_txt or ''}, P={power_txt or ''}, "
            f"motor={motor_status}, scale={scale_status}"
        )
        self.log_tab.append_line(line)


    def _apply_scada_style(self):
        # Unified sizes & SCADA-like clean look
        # (kept conservative; no fancy palette changes)
        self.setStyleSheet("""
/* ===== Base ===== */
QMainWindow {
    background: #eef1f4;
}
QWidget {
    font-size: 12px;
}

/* ===== Tabs ===== */
QTabWidget::pane {
    border: 1px solid #c7cdd6;
    top: -1px;
    background: #eef1f4;
}
QTabBar::tab {
    background: #dfe5ec;
    border: 1px solid #c7cdd6;
    border-bottom: none;
    padding: 8px 14px;
    margin-right: 2px;
    min-height: 22px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #ffffff;
}
QTabBar::tab:hover {
    background: #e7edf5;
}

/* ===== GroupBox ===== */
QGroupBox {
    background: #ffffff;
    border: 1px solid #c7cdd6;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #2b2f36;
}

/* ===== Labels ===== */
QLabel {
    color: #2b2f36;
}
QLabel#StatusText {
    font-weight: 800;
    color: #1f2630;
}

/* ===== Inputs ===== */
QLineEdit, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #b9c0cb;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #9bb7df;
}
                           QComboBox {
    background: #ffffff;
    border: 1px solid #b9c0cb;
    border-radius: 4px;
    padding: 6px 8px;
}
QComboBox:focus {
    border: 2px solid #4c84c7;
    padding: 5px 7px;
}
QLineEdit:read-only {
    background: #f3f6fa;
    color: #3a404b;
}
QLineEdit:disabled, QDoubleSpinBox:disabled {
    background: #eef2f7;
    color: #7a838f;
    border: 1px solid #cfd6df;
}

/* Clear focus ring (SCADA-friendly) */
QLineEdit:focus, QDoubleSpinBox:focus {
    border: 2px solid #4c84c7;
    padding: 5px 7px; /* compensate for thicker border */
}

/* Spinbox arrows (subtle) */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 18px;
    border-left: 1px solid #d4d9e1;
    background: #f7f9fc;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #eef3fb;
}

/* ===== CheckBox ===== */
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #9ea7b3;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #2d7bd6;
    border: 1px solid #2b6dbf;
}

/* ===== Buttons base ===== */
QPushButton {
    background: #2d7bd6;
    color: #ffffff;
    border: 1px solid #2b6dbf;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 700;
}
QPushButton:hover { background: #3a88e2; }
QPushButton:pressed { background: #2568b7; }
QPushButton:disabled {
    background: #b9c7d8;
    border: 1px solid #aab7c7;
    color: #f5f7fa;
}

/* ===== Role-based colors ===== */

/* Primary (motion / main actions) */
QPushButton[role="primary"] {
    background: #1f6fd1;
    border: 1px solid #1c5fb2;
}
QPushButton[role="primary"]:hover { background: #2a7be0; }
QPushButton[role="primary"]:pressed { background: #1a5fb7; }

/* Secondary (utility but important) */
QPushButton[role="secondary"] {
    background: #2f3a47;
    border: 1px solid #25303b;
}
QPushButton[role="secondary"]:hover { background: #3a4756; }
QPushButton[role="secondary"]:pressed { background: #25303b; }

/* Neutral (safe / service, e.g. tare/zero) */
QPushButton[role="neutral"] {
    background: #e9edf3;
    color: #1f2630;
    border: 1px solid #b9c0cb;
}
QPushButton[role="neutral"]:hover { background: #dfe6ef; }
QPushButton[role="neutral"]:pressed { background: #d2dae6; }

/* Danger (future Stop/E-Stop) — already ready to use */
QPushButton[role="danger"] {
    background: #d64545;
    border: 1px solid #b63737;
}
QPushButton[role="danger"]:hover { background: #e15353; }
QPushButton[role="danger"]:pressed { background: #b63737; }

/* ===== Scroll area ===== */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #c3c9d4;
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #aeb6c3;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ===== Status bar ===== */
QStatusBar {
    background: #dde4ee;
    border-top: 1px solid #c7cdd6;
    color: #2b2f36;
}
QStatusBar::item {
    border: none;
}
                           
QPlainTextEdit {
    background: #0f1720;
    color: #d8e0ea;
    border: 1px solid #2b3440;
    border-radius: 6px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}
/* ===== Status lamp ===== */
#StatusLamp {
    border-radius: 7px;
    border: 1px solid #6e7683;
    background: #bdbdbd; /* default */
}
#StatusLamp[state="off"]  { background: #bdbdbd; }
#StatusLamp[state="ok"]   { background: #2ecc71; }
#StatusLamp[state="warn"] { background: #f1c40f; }
#StatusLamp[state="err"]  { background: #e74c3c; }
""")

    def _build_ui(self):
        tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(tabs)

        tab = QtWidgets.QWidget()
        tabs.addTab(tab, "Main")

        self.log_tab = LogPanel()
        tabs.addTab(self.log_tab, "Log")

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
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Graceful shutdown of worker threads
        try:
            if hasattr(self, "_motor_worker"):
                self._motor_worker.disconnect_motor()
            if hasattr(self, "_scale_worker"):
                self._scale_worker.disconnect_scale()
        except Exception:
            pass
        try:
            if hasattr(self, "_motor_thread"):
                self._motor_thread.quit()
                self._motor_thread.wait(1500)
            if hasattr(self, "_scale_thread"):
                self._scale_thread.quit()
                self._scale_thread.wait(1500)
        except Exception:
            pass
        super().closeEvent(event)


def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
        print(f"Starting SCADA GUI application.... argv={sys.argv}")
        app.setStyle("Fusion")
        w = MainWindow()
        w.show()
    except KeyboardInterrupt:
        print("SCADA GUI application interrupted by user.")
        sys.exit(0)

    except Exception as ex:
        print(f"ERROR starting SCADA GUI application. Exception: {ex} of type: {type(ex)}.")
        sys.exit(1)
    _exit_code = app.exec()
    print(f"SCADA GUI application exited with code {_exit_code}.")
    sys.exit(_exit_code)


if __name__ == "__main__":
    main()
