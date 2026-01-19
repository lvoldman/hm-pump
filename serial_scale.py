from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl
from WLCscale import WLCscale, WLCscaleStub
import threading    
import time
from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack

Scale = WLCscale

class serialScale(QObject):
    weightChanged = Signal(float)
    connectionChanged = Signal(bool)

    @staticmethod
    def listScales() -> list[str]:
        return Scale.listScales()

    def __init__(self, serial_port: str, poll_interval: float = 0.1, parent=None):
        super().__init__(parent)
        self._port = serial_port
        self._weight = 0.0
        self._connected = False
        self._poll_interval = poll_interval
        self._scale = Scale(serial_port, poll_interval)
        self.__wd:threading.Thread | None = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__wd_stop.clear()
        self._watch_dog_run()

    def __del__(self):
        self.__wd_stop.set()
        self.disconnect()

    def __repr__(self):
        return f'serialScale(port={self._port})'

    @Property(float, notify=weightChanged)
    def weight(self):
        return self._scale.weight

    @Property(bool, notify=connectionChanged)
    def isConnected(self):
        return self._scale.is_connected()

    @Slot(str)
    def update_serial_port(self, port: str):
        self._port = port
        self._scale.update_serial_port(port)
        self.connectionChanged.emit(self.isConnected)

    @Slot(float)
    def update_poll_interval(self, interval: float):
        self._poll_interval = interval
        self._scale.update_poll_interval(interval)

    @Slot(bool, result=bool)
    def connect(self, dummy=True) -> bool:
        self._connected = True
        self._scale.connect()
        self.connectionChanged.emit(True)
        return True
    
    def  _watch_dog_run(self)->threading.Thread:
        print_log(f'Running whatch dog thread')         
        self.__wd = threading.Thread(target=self.__watch_dog_thread , daemon=True)
                                                        # Start watchdog thread
        self.__wd.start()   
        return self.__wd
        
    def __watch_dog_thread(self):
        print_log(f'Watch dog thread started')
        try:
            while not self.__wd_stop.is_set():
                self.connectionChanged.emit(self.isConnected)                                # Monitor operation status
                self.weightChanged.emit(self.weight)
                time.sleep(self._poll_interval)
            print_log(f'Watch dog thread stopped with weight={self.weight}')
        except Exception as e:
            print_log(f'Error in watch dog thread: {e}')
            exptTrace(e)