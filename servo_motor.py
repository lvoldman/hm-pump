from queue import Queue
import threading
from enum import Enum
from dataclasses import dataclass
import time
from maxon import MAXON_Motor, MAXON_Motor_Stub          # Assuming maxon is a module for servo motor control
from PySide6.QtCore import QObject, Signal, Property, Slot, QUrl
from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack
from shiboken6 import isValid

motServo = MAXON_Motor_Stub # For testing purposes, replace with MAXON_Motor for actual implementation

@dataclass
class servoParameters:
    velocity: float | None = None                  # Velocity in units per second
    acceleration: float | None = None              # Acceleration in units per second squared
    deceleration: float | None = None              # Deceleration in units per second squared
    stall: bool = False                      # Whether to enable stall detection
    home_velocity: float | None = None             # Velocity for homing operation
    home_acceleration: float | None = None         # Acceleration for homing operation
    timeout: float | None = None                    # Timeout for operations in seconds

class servoMotor(QObject):
    class mState(Enum):
        OFF = "OFF"
        IDLE = "IDLE"
        RUNNING = "RUNNING"
        WARNING = "WARNING"
        ERROR = "ERROR"
    opType = Enum("opType", ["forward", "backward", "go2pos", "stoped"])
    _motors = list[MAXON_Motor.portSp]
    stateChanged = Signal(str)          # "OFF", "IDLE", "RUNNING", "WARNING", "ERROR"
    positionChanged = Signal(int)       # Current position in units
    operationFinished = Signal(bool, str)  # success, message

    @staticmethod
    def listMotors()->list[str]:       # List available servo motors SNs
        servoMotor._motors = motServo.init_devices()      
        sn_motors:list[str] = list()

        for m in servoMotor._motors:
            sn_motors.append(m.sn)
        return  sn_motors
    
    def __init__(self, serial_number:str):
        self.devNotificationQ:Queue = Queue()           # Queue for notifications from watchdog thread 
                                                        # when opeartion completes
        self.__wd:threading.Thread | None = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__position:int = 0                             # Current position of servo motor
        self.__current_op:servoMotor.opType = servoMotor.opType.stoped          # Current operation
        self.__op_lock:threading.Lock = threading.Lock()  # Lock for current operation
        self.__start_time:float = 0.0                     # Start time of current operation
        self.serial_number = serial_number                # Serial number of the servo motor
        self.__wd_stop.clear()
        self.__timeout:float | None = None                  # Timeout for operations
                    
        self._state = servoMotor.mState.OFF.value
        try:
            for m in servoMotor._motors:
                if m.sn == serial_number:
                    self.__motor = motServo(m)          # Initialize motor instance
                    break
            else:
                raise ValueError(f'Servo motor with serial number {serial_number} not found')
            
            self.__position = self.__motor.mDev_get_cur_pos()
            self._watch_dog_run()
        except Exception as ex:
            print_err(f'Error initializing servo motor {serial_number}: {ex}')
            exptTrace(ex)
            if self.__motor:
                del self.__motor
                self.__motor = None

        
    def __repr__(self):
        return f'servoMotor(SN={self.serial_number})'


    @Property(int, notify=positionChanged)
    def position(self) -> int:
        self.__position = self.__motor.mDev_get_cur_pos()
        return self.__position
    
    @Slot(int, servoParameters, result=bool)
    def go2pos(self, new_position, _parms: servoParameters)->bool:
        try:
            self.__start_time = time.time()                 # Record start time of operation
            self._state = servoMotor.mState.RUNNING.value
            self.stateChanged.emit(self._state)
            self.__timeout = _parms.timeout
            self.__motor.go2pos(new_position, 
                                velocity=_parms.velocity,
                                acceleration=_parms.acceleration,
                                deceleration=_parms.deceleration,
                                stall=_parms.stall)
            self.positionChanged.emit(self.position)
            print_DEBUG(f'go2pos command issued to position {new_position} with parms: {_parms}')

        except Exception as ex:
            print_err(f'Error in go2pos: {ex}')
            exptTrace(ex)
            return False
        
        with self.__op_lock:
            self.__current_op = servoMotor.opType.go2pos   # Update current operation
        return True

    @Slot(servoParameters, result=bool)
    def forward(self, _parms: servoParameters)->bool:
        try:
            self.__start_time = time.time()                 # Record start time of operation
            self._state = servoMotor.mState.RUNNING.value
            self.stateChanged.emit(self._state)
            self.__timeout = _parms.timeout
            self.__motor.mDev_forward(velocity=_parms.velocity,
                                acceleration=_parms.acceleration,
                                deceleration=_parms.deceleration,
                                timeout=_parms.timeout,
                                polarity=None,
                                stall=_parms.stall)
            self.positionChanged.emit(self.position)
        except Exception as ex:
            print_err(f'Error in forward: {ex}')
            exptTrace(ex)
            return False
        with self.__op_lock:
            self.__current_op = servoMotor.opType.forward   # Update current operation
        return True
    
    @Slot(servoParameters, result=bool)
    def backward(self, _parms: servoParameters)->bool:
        try:
            self.__start_time = time.time()                 # Record start time of operation
            self._state = servoMotor.mState.RUNNING.value
            self.stateChanged.emit(self._state)
            self.__timeout = _parms.timeout
            self.__motor.mDev_backward(velocity=_parms.velocity,
                                  acceleration=_parms.acceleration,
                                  deceleration=_parms.deceleration,
                                  timeout=_parms.timeout,
                                  polarity=None,
                                  stall=_parms.stall)
            self.positionChanged.emit(self.position)
            self.operationFinished.emit(True, "Reached")
        except Exception as ex:
            print_err(f'Error in backward: {ex}')
            exptTrace(ex)
            return False
        with self.__op_lock:
            self.__current_op = servoMotor.opType.backward   # Update current operation
        return True
    

    def __del__(self):
        if self._state == servoMotor.mState.RUNNING.value:
            self.stop()
        self.__wd_stop.set()                      # Signal watchdog thread to stop
        if self.__motor:
            del self.__motor



    @Slot(bool, result=bool)
    def stop(self, _status:bool | None=None)->bool:                               # atomic stop operation (no watchdog)
        print_log(f'Stopping motor {self.serial_number}')
        try:
            if _status is None:
                _status = self.__motor.mDev_stop()
            # Unblock any waiters (best-effort)
            self._state = servoMotor.mState.IDLE.value
            if isValid(self):                                                   # Check if the QObject is still valid
                self.stateChanged.emit(self._state)
                self.positionChanged.emit(self.position)
                self.operationFinished.emit(True, "Stopped")
            else:
                print("Object Qt already deleted, skipping emit")

            self.devNotificationQ.put(_status)         # Notify operation completion
        except Exception as ex:
            print_err(f'Error in stop: {ex}')
            exptTrace(ex)
        return _status

    def  _watch_dog_run(self)->threading.Thread:
        print_log(f'Running whatch dog thread')         
        self.__wd = threading.Thread(target=self.__watch_dog_thread , daemon=True)
                                                        # Start watchdog thread
        self.__wd.start()   
        return self.__wd
        
    def __watch_dog_thread(self):
        print_log(f'Watch dog thread started')
        _status = True
        try:
            while not self.__wd_stop.is_set():
                self.positionChanged.emit(self.position)                                # Monitor operation status

                if self._state == servoMotor.mState.RUNNING.value:
                    if self.__timeout is not None:
                        if (time.time() - self.__start_time) > self.__timeout:
                            print_log(f'Operation timed out')
                            _status = True
                            self.stop()
                        if self.__motor.devNotificationQ.qsize() > 0:
                            _status = self.__motor.devNotificationQ.get()
                            print_log(f'Operation completed with status {_status}')
                            self.stop()

                time.sleep(0.1)
            print_log(f'Watch dog thread stopped at position {self.__position}')
        except Exception as e:
            print_log(f'Error in watch dog thread: {e}')
            _status = False

        with self.__op_lock:    
            self.__current_op = servoMotor.opType.stoped         # Update current operation

        self.devNotificationQ.put(_status)          # Notify operation completion
