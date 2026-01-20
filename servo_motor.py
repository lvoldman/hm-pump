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

    _motors:list[MAXON_Motor.portSp] | None = None      # Class variable to hold available motors

    stateChanged = Signal(str)          # "OFF", "IDLE", "RUNNING", "WARNING", "ERROR"
    positionChanged = Signal(int)       # Current position in units
    operationFinished = Signal(bool, str)  # success, message

    currentMotorChanged = Signal()      # Signal emitted when current motor changes - 
                                        # NOTE: Added for consistency with MotorController


    @staticmethod
    def listMotors()->list[str]:       # List available servo motors SNs
        servoMotor._motors = motServo.init_devices()      
        sn_motors:list[str] = list()

        for m in servoMotor._motors:
            sn_motors.append(m.sn)
        return  sn_motors
    
    def __init__(self, serial_number:str = None, parent=None):
        super().__init__(parent)
        self.devNotificationQ:Queue = Queue()           # Queue for notifications from watchdog thread 
                                                        # when opeartion completes
        self.__wd:threading.Thread | None = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__position:int = 0                             # Current position of servo motor
        self.__current_op:servoMotor.opType = servoMotor.opType.stoped          # Current operation
        self.__op_lock:threading.Lock = threading.Lock()  # Lock for current operation
        self.__start_time:float = 0.0                     # Start time of current operation
        self._current_sn:str | None = None
        self.__current_motor:MAXON_Motor.portSp | None = None    # Sp of the servo motor
        self.__wd_stop.clear()
        self.__timeout:float | None = None                  # Timeout for operations
        self.__motor:motServo | None = None

                    
        self._state = servoMotor.mState.OFF.value
        if servoMotor._motors is None:
            servoMotor.listMotors()
            print_log(f'Listing available servo motors for first time...')


        self._current_sn = serial_number if serial_number else (servoMotor._motors[0].sn if servoMotor._motors else '') 
        # print_log(f'Available servo motors->{servoMotor._motors}, s/n selected={self._current_sn}')
        print_log('Available servo motors->%s, s/n selected=%s', str(servoMotor._motors), self._current_sn)

        try:
            for m in servoMotor._motors:
                if m.sn == self._current_sn:
                    self.__motor = motServo(m)          # Initialize motor instance
                    self.__current_motor = m
                    break
            else:
                raise ValueError(f'Servo motor with serial number {self._current_sn} not found')
            
            self.__position = self.__motor.mDev_get_cur_pos()
            self._watch_dog_run()
        except Exception as ex:
            print_err(f'Error initializing servo motor {self._current_sn}: {ex}')
            exptTrace(ex)
            if self.__motor:
                del self.__motor
                self.__motor = None

        
    def __repr__(self):
        return f'servoMotor(SN={self._current_sn})'

    @Property(list, constant=True)
    def availableMotors(self):              # list of available motor serial numbers
        print_DEBUG(f'Getting available motors: {servoMotor._motors}')
        return servoMotor._motors

    @Property(str, notify=currentMotorChanged)
    def currentSerialNumber(self) -> str:
        print_DEBUG(f'Getting current serial number: {self._current_sn}')
        return self._current_sn

    @currentSerialNumber.setter
    def currentSerialNumber(self, sn: str):
        print_DEBUG(f'Setting current serial number from {self._current_sn} to {sn}')
        try:
            if sn != self._current_sn:
                self._current_sn = sn
                del self.__motor
                for m in servoMotor._motors:
                    if m.sn == sn:
                        self.__motor = motServo(m)          # Initialize motor instance
                        break
                    else:
                        raise ValueError(f'Servo motor with serial number {sn} not found')
                self.currentMotorChanged.emit()
        except Exception as ex:
            print_err(f'Error changing current motor to {sn}: {ex}')
            exptTrace(ex)

    @Property(int, notify=positionChanged)
    def position(self) -> int:
        self.__position = self.__motor.mDev_get_cur_pos()
        return self.__position
    
    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state
    
    # ----- Compatability with MotorController interface -----
    @Slot(float, float, float, result=bool)
    def moveAbsolute(self, position: float, vel: float, acc: float)->bool:   # Move to absolute position
                                                                        # for compatibility with MotorController
        print_log(f'Move absolute command received in MotorController for motor:{self} to position {position} with vel={vel}, acc={acc}')   
        if not self.__motor:
            print_err('No motor initialized')
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self.go2pos(position, params)
        return True
    
    @Slot(result=bool)
    def stop(self)->bool:
        print_log(f'Stop command received in MotorController for motor:{self}')
        if not self.__motor:
            print_err('No motor initialized')
            return False
        print_log(f'Stop command received in MotorController for motor:{self._current_sn} // {self.__motor.mDev_SN}')
        self.stopMotor()
        return True
    
    @Slot(result=bool)
    def moveForward(self, vel: float, acc: float)->bool:
        print_log(f'Move forward command received in MotorController for motor:vel={vel}, acc={acc}  motor:{self}')
        if not self.__motor:
            print_err('No motor initialized')
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self.forward(params)
        return True
    
    @Slot(result=bool)
    def moveBackward(self, vel: float, acc: float)->bool:
        print_log(f'Move backward command received in MotorController for motor:vel={vel}, acc={acc}  motor:{self}')
        if not self.__motor:
            print_err('No motor initialized')
            return False
        params = servoParameters(velocity=vel, acceleration=acc)
        self.backward(params)
        return True
    
    
    def getPosition(self)->float:
        if not self.__motor:
            return 0.0
        
        return self.position 

    # ---------------------------------------------------------
    @Slot(result=bool)
    def home(self)->bool:
        try:
            if not self.__motor:
                print_err('No motor initialized')
                return False    
            self.__motor.mDev_reset_pos()
            print_DEBUG(f'home command issued')
            return True
        except Exception as ex:
            print_err(f'Error in home: {ex}')
            exptTrace(ex)
            return False


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
    def stopMotor(self, _status:bool | None=None)->bool:                               # atomic stop operation (no watchdog)
        print_log(f'Stopping motor {self._current_sn}')
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
                print_err("Object Qt already deleted, skipping emit")

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
            exptTrace(e)
            _status = False

        with self.__op_lock:    
            self.__current_op = servoMotor.opType.stoped         # Update current operation

        self.devNotificationQ.put(_status)          # Notify operation completion
