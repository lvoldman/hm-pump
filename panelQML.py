__author__ = "Leonid Voldman"
__created_on__ = "2026-01-07"  
__copyright__ = "Copyright 2026"
__credits__ = ["VoldmanTech"]
__license__ = "SLA"
__version__ = "1.0.0"
__maintainer__ = "Leonid Voldman"
__email__ = "vleonid@voldman.com"
__status__ = "production"

import logging
import sys
import platform
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

class AppInfo(QObject):
    @Property(str, constant=True)
    def version(self):
        return __version__
    
    @Property(str, constant=True)
    def pythonVersion(self):
        return platform.python_version()
    
    @Property(str, constant=True)
    def pySideVersion(self):
        return PySide6.QtCore.qVersion()
    
    @Property(str, constant=True)
    def cpuLoad(self):
        try:
            import psutil
            return f"{psutil.cpu_percent()} %"
            # return f"{psutil.cpu_percent()}"
        except ImportError:
            # return "psutil not installed"
            return "load data is unavailable"

    
    
    

# ─── Application run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    
    

    app = QApplication(sys.argv)                # Create the application instance, argv list from command line
                                                # and pass it to QApplication

    engine = QQmlApplicationEngine()        # Create QML application engine

    # Register context objects
    motor_ctrl = servoMotor()                   # Create motor controller object
    scale = serialScale()                    # Create scale controller object  
    appInfo = AppInfo()                      # Create application info object

    # Set context properties for QML
    engine.rootContext().setContextProperty("motorController", motor_ctrl)
    engine.rootContext().setContextProperty("scaleController", scale)
    engine.rootContext().setContextProperty("appInfo", appInfo)
    
    # Connect aboutToQuit signal to cleanup functions 
    app.aboutToQuit.connect(motor_ctrl.stopMotor)
    app.aboutToQuit.connect(scale.disconnect)

    # Load QML file and start the application
    qml_file = Path(__file__).parent / "panelQML.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))       # Load the QML file
    

    logging.shutdown()  # Ensure all logging messages are flushed before checking root objects
    
    if not engine.rootObjects():        # Check if root objects are loaded correctly
        sys.exit(-1)

    sys.exit(app.exec())            # Start the application event loop and exit on completion