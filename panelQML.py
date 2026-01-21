None# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl

import os
os.environ["QT_LOGGING_RULES"] = "qt.qml.binding.debug=true;qt.remoteobjects.debug=true"

from dataclasses import dataclass
from queue import Queue

from servo_motor import servoMotor, servoParameters
from serial_scale import serialScale

from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack



# ─── Запуск приложения ─────────────────────────────────────────────────────
if __name__ == "__main__":
    
    

    app = QApplication(sys.argv)

    engine = QQmlApplicationEngine()

    # Регистрируем контекстные объекты
    motor_ctrl = servoMotor()
    scale = serialScale()

    engine.rootContext().setContextProperty("motorController", motor_ctrl)
    engine.rootContext().setContextProperty("scaleController", scale)

    qml_file = Path(__file__).parent / "panelQML.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())