from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl
from WLCscale import WLCscale, WLCscaleStub
import threading    
import time
from collections import deque

from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack

# Scale = WLCscaleStub  # For testing without actual scale, replace with WLCscale for real scale
Scale = WLCscale         # For production


class serialScale(QObject):
    weightChanged = Signal(float)
    # counterChanged = Signal(int)      # for future use if we want to track number of weight updates
    rocChanged = Signal()
    connectionChanged = Signal(bool)
    currentPortChanged = Signal()   # Signal emitted when current port changes (for compatibility)
    # _ports: list[str] | None = None
    _scales: list[str] | None = None

    @staticmethod
    def listScales() -> list[str]:
        serialScale._scales = Scale.listScales()
        return serialScale._scales

    def __init__(self, serial_port: str = None, poll_interval: float = 0.1, parent=None):
        super().__init__(parent)
        # self._port = serial_port if serial_port else (serialScale.listScales()[0] if serialScale.listScales() else "")
        self._weight = 0.0
        self.__last_weight = 0                          # For calculating rate of change (ROC)
        self.__last_time = time.time()                  # For calculating rate of change (ROC)
        self.__last_roc = 0.0                            # Store last ROC value to return if time difference is zero
        self._connected: bool = False                       # Connection status
        self._poll_interval = poll_interval                     # Polling interval for watchdog
        self._scale:Scale | None = None             # Scale instance
        self.__wd:threading.Thread | None = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        # Queue for smoothing delta (up to 10 samples)
        self.delta_history = deque(maxlen=10)
        self.smooth_delta = 0
        self.delta_history.clear()

        self.__wd_stop.clear()  
        self._watch_dog_run()

        # self.weightChanged.connect(self.rocChanged)   # Automatically update ROC when weight or counter changes, 
                                                        # can be used if we want to calculate ROC on weight change instead of time-based polling
                                                        # Note: If we calculate ROC on weight change, we need to ensure that weight updates are 
                                                        # frequent enough to get accurate ROC, and we may want to add a timer-based update as well to 
                                                        # handle cases where weight doesn't change but we still want to update ROC based on time.
        # self.counterChanged.connect(self.rocChanged)


        if serialScale._scales is None:
            print_log('Listing scales for the first time in serialScale init')
            serialScale._scales = serialScale.listScales()


        self._port = serial_port if serial_port else (serialScale._scales[0] if serialScale._scales else "")

        print_log(f'Available scales: {serialScale._scales}, requested port: {self._port}')

        if not self._port:
            print_err('No serial port specified and no scales found')
            return

        if self._port not in serialScale._scales:
            raise ValueError(f'Serial scale with port {self._port} not found among available ports: {serialScale._scales}')
        
        if self._port:
            self._scale = Scale(self._port, poll_interval)
        else:
            raise ValueError('No serial port specified for serialScale')
        
        if self._port and self._scale is not None:
            self.connect( ) 

        self._connected = self.isConnected

    def __del__(self):
        self.disconnect()

    def __repr__(self):
        return f'serialScale(port={self._port})'
    
    # ----------- Compatibility with ScaleController interface -----------


    
    @Property(str, notify=currentPortChanged)
    def currentSerialPort(self) -> str:
        print_DEBUG(f'Getting current serial port: {self._port}')
        return self._port if self._port else ""

    @currentSerialPort.setter
    def currentSerialPort(self, port: str):
        print_DEBUG(f'Setting current serial port from {self._port} to {port}')
        self.delta_history.clear()

        if port != self._port:
            self._port = port
            self._scale = serialScale(port)
            # self.currentPortChanged.emit(self._scale.isConnected if self._scale else False)
            self.currentPortChanged.emit()

    # @Property(list, constant=True)
    @Property(list, notify=currentPortChanged)
    def availablePorts(self):              # list of available serial ports
        print_DEBUG(f'Getting available serial ports: {serialScale._scales}')
        return serialScale._scales if serialScale._scales is not None else []
    

    # -----------------------

    @Property(float, notify=weightChanged)
    def weight(self):
        # print_DEBUG(f'W={self._scale.weight if self._scale else 0.0}')
        return self._scale.weight / 1000 if self._scale else 0.0    # Convert to kg for better readability, adjust as needed 
                                                                    # (e.g., keep in grams, convert litters, etc.)


    def calcilateSmoothROC(self):
        __time = time.time()
        new_weight = self._scale.weight if self._scale else 0.0  # Get current weight, if scale is not available, assume weight is zero 
                                                                # (or we could choose to return None or some error value)
        
        if new_weight== 0:          # If weight is zero, we can assume that the scale is either not connected or not reading properly, 
                                    # so we return 0 for ROC to avoid misleading values.
            return 
        
        _roc:float = 0
        if __time != self.__last_time:          # Avoid division by zero 
            _roc = (new_weight - self.__last_weight) / (__time - self.__last_time) 

        else:
            return 

        self.delta_history.append(_roc)

        self.smooth_delta = sum(self.delta_history) / len(self.delta_history)   # Simple moving average for smoothing, adjust as needed 
                                                                                # (e.g., weighted average, exponential smoothing, etc.)

        # print_DEBUG(f'ROC = {_roc}, {new_weight}-{self.__last_weight} = {new_weight - self.__last_weight} gr, time_diff={__time - self.__last_time if self.__last_time else "N/A"} P={self.smooth_delta}, len = {len(self.delta_history)}')

        self.__last_weight = new_weight 
        self.__last_time = __time
        self.__last_roc = _roc

        return 






    @Property(float, notify=rocChanged)
    def ROC(self):
        return self.smooth_delta / 1000  * 60  # Convert to per minute for better readability, adjust as needed


    @Property(bool, notify=connectionChanged)
    def isConnected(self):
        self._connected = self._scale.is_connected() if self._scale else False
        # print_DEBUG(f'Checking connection status for scale on port {self._port}: {self._scale} ->{self._scale.is_connected() if self._scale else False}')
        return self._connected
    
    @Slot(result=bool)
    def disconnect(self)->bool:
        try:
            if not self._scale:
                print_warn('No scale instance to disconnect')
                return False
            
            self.__wd_stop.set()
            if self.__wd and self.__wd.is_alive():
                print_log('Waiting for watchdog thread to stop...')
                self.__wd.join(timeout=1.0)
                if self.__wd.is_alive():
                    print_warn('Watchdog thread did not stop in time')
                else:
                    print_log('Watchdog thread stopped successfully')
        
                print_log(f'Disconnecting scale on port {self._port}')
                if self._scale and self._scale.is_connected():
                    self._scale.disconnect()
                self._connected = False
                self.connectionChanged.emit(False)        
        
        except Exception as e:
            print_warn(f'Error while stopping watchdog thread: {e}')
            exptTrace(e)
            return False
        
        return True
        


    @Slot(str)
    def update_serial_port(self, port: str):
        print_DEBUG(f'Updating serial port to {self._port}-> {port}')
        if not self._scale:
            print_err(f'No scale instance to update port to {port}')
            return
        self._port = port
        self._scale.update_serial_port(port)
        self.connectionChanged.emit(self.isConnected)

    @Slot(float)
    def update_poll_interval(self, interval: float):
        self._poll_interval = interval
        if self._scale:
            self._scale.updatePollInterval(interval)

    @Slot(result=bool)
    def connect(self) -> bool:
        if not self._scale:
            print_err('No scale instance to connect')
            return False
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
        while True:
            try:
                self.connectionChanged.emit(self.isConnected)                                # Monitor operation status

                if self._scale and self._scale.is_connected():
                    self.weightChanged.emit(self.weight)
                else:
                    if self._scale:                 # connection lost, but we have a scale instance, so we can try to reconnect
                        print_warn(f'Scale on port {self._port} is not connected or not available. Reconnecting...')
                        self.connect()

                self.calcilateSmoothROC()  # Update ROC based on current weight and time, this will update self.smooth_delta which is returned by ROC property
                self.rocChanged.emit()
                if self.__wd_stop.wait(float(self._poll_interval)):
                    break
                # time.sleep(self._poll_interval)
            except Exception as e:
                print_log(f'Error in watch dog thread: {e}')
                exptTrace(e)
        
        print_log(f'Watch dog thread stopped with weight={self.weight}')
