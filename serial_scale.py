from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl
from WLCscale import WLCscale, WLCscaleStub
import threading    
import time
from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack

Scale = WLCscaleStub  # For testing without actual scale, replace with WLCscale for real scale

class serialScale(QObject):
    weightChanged = Signal(float)
    connectionChanged = Signal(bool)
    currentPortChanged = Signal()   # Signal emitted when current port changes (for compatibility)
    _ports: list[str] | None = None
    _scales: list[str] | None = None

    @staticmethod
    def listScales() -> list[str]:
        serialScale._scales = Scale.listScales()
        return serialScale._scales

    def __init__(self, serial_port: str = None, poll_interval: float = 0.1, parent=None):
        super().__init__(parent)
        self._port = serial_port if serial_port else (serialScale.listScales()[0] if serialScale.listScales() else "")
        self._weight = 0.0
        self._connected: bool = False
        self._poll_interval = poll_interval
        self._scale:Scale | None = None
        self.__wd:threading.Thread | None = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__wd_stop.clear()
        self._watch_dog_run()

        if serialScale._scales is None:
            serialScale._scales = serialScale.listScales()

        if self._port not in serialScale._scales:
            raise ValueError(f'Serial scale with port {self._port} not found among available ports: {serialScale._scales}')
        
        if self._port is not None:
            self._scale = Scale(self._port, poll_interval)
        else:
            raise ValueError('No serial port specified for serialScale')
        self._connected = self.isConnected

    def __del__(self):
        self.__wd_stop.set()
        self.disconnect()

    def __repr__(self):
        return f'serialScale(port={self._port})'
    
    # ----------- Compatibility with ScaleController interface -----------

    @Property(list, constant=True)
    def availablePorts(self):              # list of available motor serial numbers
        print_DEBUG(f'Getting available serial ports: {serialScale._scales}')
        return serialScale._scales 
    
    @Property(str, notify=currentPortChanged)
    def currentSerialPort(self) -> str:
        return self._port

    @currentSerialPort.setter
    def currentSerialPort(self, port: str):
        if port != self._port:
            self._port = port
            self._scale = serialScale(port)
            # self.currentPortChanged.emit(self._scale.isConnected if self._scale else False)
            self.currentPortChanged.emit()

    # @Property(list, constant=True)
    @Property(list, notify=currentPortChanged)
    def availablePorts(self):              # list of available serial ports
        return serialScale._ports
    # -----------------------

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
        self._scale.updatePollInterval(interval)

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