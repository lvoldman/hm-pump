None# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl

from dataclasses import dataclass
from queue import Queue
from typing import List, Optional

from servo_motor import servoMotor, servoParameters
from serial_scale import serialScale

from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack


# ─── Controllers for QML ────────────────────────────────
class MotorController(QObject):
    currentMotorChanged = Signal()      # Signal emitted when current motor changes

    def __init__(self, parent=None):
        super().__init__(parent)                
        self._motors: List[str] = servoMotor.listMotors()
        self._current_sn: str = self._motors[0] if self._motors else ""
        self._motor: servoMotor | None = servoMotor(self._current_sn) if self._current_sn else None

    def __del__(self):
        if self._motor:
            del self._motor

    @Property(list, constant=True)
    def availableMotors(self):              # List of available motor serial numbers
        return self._motors

    @Property(str)
    def currentSerialNumber(self) -> str:
        return self._current_sn

    @currentSerialNumber.setter
    def currentSerialNumber(self, sn: str):
        if sn != self._current_sn:
            self._current_sn = sn
            del self._motor
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
        print_log(f'Stop command received in MotorController for motor:{self._motor}')
        if not self._motor:
            return False
        print_log(f'Stop command received in MotorController for motor:{self._motor.serial_number}')
        self._motor.stop()
        return True
    
    @Slot(result=bool)
    def moveForward(self, vel: float, acc: float):
        print_log(f'Move forward command received in MotorController for motor:vel={vel}, acc={acc}  motor:{self._motor}')
        if not self._motor:
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self._motor.forward(params)
        return True
    
    @Slot(result=bool)
    def moveBackward(self, vel: float, acc: float):
        print_log(f'Move backward command received in MotorController for motor:vel={vel}, acc={acc}  motor:{self._motor}')
        if not self._motor:
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self._motor.backward(params)
        return True
    
    
    def getPosition(self)->float:
        if not self._motor:
            return 0.0
        return self._motor.position
    
    

class ScaleController(QObject): 
    currentPortChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        _ports = serialScale.listScales()
        self._port = _ports[0] if _ports else ""
        self._scale: serialScale | None =  serialScale(self._port) if len(self._port) > 0 else None
        self._weight = 0.0
        self._connected = self._scale.isConnected if self._scale else False

    @Property(str)
    def currentSerialPort(self) -> str:
        return self._port

    @currentSerialPort.setter
    def currentSerialPort(self, port: str):
        if port != self._port:
            self._port = port
            self._scale = serialScale(port)
            self.currentPortChanged.emit(self._scale.isConnected if self._scale else False)

    @Property(list, constant=True)
    def availablePorts(self):              # List of available serial ports
        return self._ports
    
    def weight(self)->float:
        if not self._scale:
            return 0.0
        return self._scale.weight

# ─── Запуск приложения ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)

    engine = QQmlApplicationEngine()

    # Регистрируем контекстные объекты
    motor_ctrl = MotorController()
    scale = ScaleController()

    engine.rootContext().setContextProperty("motorController", motor_ctrl)
    engine.rootContext().setContextProperty("scale", scale)

    qml_file = Path(__file__).parent / "panelQML.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())