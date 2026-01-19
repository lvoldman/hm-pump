None# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl

# ─── Заглушки / примеры ваших классов ──────────────────────────────────────
from dataclasses import dataclass
from queue import Queue
from typing import List, Optional

from servo_motor import servoMotor, servoParameters
from serial_scale import serialScale

@dataclass
class servoParameters:
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    deceleration: Optional[float] = None
    stall: bool = False
    home_velocity: Optional[float] = None
    home_acceleration: Optional[float] = None
    timeout: Optional[float] = None

class servoMotor(QObject):
    stateChanged = Signal(str)          # "OFF", "IDLE", "RUNNING", "WARNING", "ERROR"
    positionChanged = Signal(int)
    operationFinished = Signal(bool, str)  # success, message

    @staticmethod
    def listMotors() -> List[str]:
        return ["MTR-001", "MTR-042", "MTR-777"]

    def __init__(self, serial_number: str, parent=None):
        super().__init__(parent)
        self._serial = serial_number
        self._position = 0
        self._state = "OFF"

    @Property(int, notify=positionChanged)
    def position(self):
        return self._position

    @Slot(servoParameters)
    def go2pos(self, params: servoParameters):
        print(f"Moving to position with v={params.velocity}, a={params.acceleration}")
        self._state = "RUNNING"
        self.stateChanged.emit(self._state)
        # ... здесь реальная команда ...
        self._position += 1000  # имитация
        self.positionChanged.emit(self._position)
        self.operationFinished.emit(True, "Reached")

    @Slot()
    def stop(self):
        self._state = "IDLE"
        self.stateChanged.emit(self._state)

    # другие методы...


class serialScale(QObject):
    weightChanged = Signal(float)
    connectionChanged = Signal(bool)

    @staticmethod
    def listScales() -> List[str]:
        return ["COM3", "COM4", "/dev/ttyUSB0"]

    def __init__(self, serial_port: str = "", poll_interval: float = 0.1, parent=None):
        super().__init__(parent)
        self._port = serial_port
        self._weight = 0.0
        self._connected = False
        self._poll_interval = poll_interval

    @Property(float, notify=weightChanged)
    def weight(self):
        return self._weight

    @Property(bool, notify=connectionChanged)
    def isConnected(self):
        return self._connected

    @Slot(str)
    def update_serial_port(self, port: str):
        self._port = port

    @Slot(float)
    def update_poll_interval(self, interval: float):
        self._poll_interval = interval

    @Slot(bool, result=bool)
    def connect(self, dummy=True) -> bool:
        self._connected = True
        self.connectionChanged.emit(True)
        return True


# ─── Контроллеры для удобной работы из QML ────────────────────────────────
class MotorController(QObject):
    currentMotorChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._motors = servoMotor.listMotors()
        self._current_sn = self._motors[0] if self._motors else ""
        self._motor = servoMotor(self._current_sn) if self._current_sn else None

    @Property(list, constant=True)
    def availableMotors(self):
        return self._motors

    @Property(str)
    def currentSerialNumber(self):
        return self._current_sn

    @currentSerialNumber.setter
    def currentSerialNumber(self, sn: str):
        if sn != self._current_sn:
            self._current_sn = sn
            self._motor = servoMotor(sn)
            self.currentMotorChanged.emit()

    @Slot(float, float, float, result=bool)
    def moveAbsolute(self, position: float, vel: float, acc: float):
        if not self._motor:
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self._motor.go2pos(params)
        return True

    @Slot(result=bool)
    def stop(self):
        print(f'Stop command received in MotorController for motor:{self._motor}')
        if not self._motor:
            return False
        print(f'Stop command received in MotorController for motor:{self._motor.serial_number}')
        self._motor.stop()
        return True

    # другие методы...


# ─── Запуск приложения ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)

    engine = QQmlApplicationEngine()

    # Регистрируем контекстные объекты
    motor_ctrl = MotorController()
    scale = serialScale()

    engine.rootContext().setContextProperty("motorController", motor_ctrl)
    engine.rootContext().setContextProperty("scale", scale)

    qml_file = Path(__file__).parent / "panelQML.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())