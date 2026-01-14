from queue import Queue
import threading
from enum import Enum
from dataclasses import dataclass
import time


@dataclass
class servoParameters:
    velocity: float = None                  # Velocity in units per second
    acceleration: float = None              # Acceleration in units per second squared
    deceleration: float = None              # Deceleration in units per second squared
    stall: bool = False                      # Whether to enable stall detection
    home_velocity: float = None             # Velocity for homing operation
    home_acceleration: float = None         # Acceleration for homing operation
    timeout: float = None                    # Timeout for operations in seconds


class servoMotor:
    opType = Enum("opType", ["forward", "backward", "go2pos", "stoped"])

    @staticmethod
    def listMotors()->list[str]:       # List available servo motors SNs
        _motors = []
        pass                  # Implement logic to list available servo motors
        return  _motors
    
    def __init__(self):
        self.devNotificationQ:Queue = Queue()           # Queue for notifications from watchdog thread 
                                                        # when opeartion completes
        self.__wd:threading.Thread = None                  # Watchdog thread
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__position:int = 0                             # Current position of servo motor
        self.__current_op:servoMotor.opType = servoMotor.opType.stoped          # Current operation
        self.__op_lock:threading.Lock = threading.Lock()  # Lock for current operation
        self.__start_time:float = 0.0                     # Start time of current operation
        self.__wd_stop.clear()


    @property
    def position(self) -> int:
        return self.__position
    
    def go2pos(self, new_position, _parms: servoParameters)->bool:
        try:
            pass                   # Implement go to position logic here
        except Exception as e:
            print(f'Error in go2pos: {e}')
            return False
        
        with self.__op_lock:
            self.__current_op = servoMotor.opType.go2pos   # Update current operation
        self._watch_dog_run(_parms.timeout)

    def forward(self, _parms: servoParameters)->bool:
        try:
            pass                   # Implement  forward logic here
        except Exception as e:
            print(f'Error in go2pos: {e}')
            return False
        with self.__op_lock:
            self.__current_op = servoMotor.opType.forward   # Update current operation
        self._watch_dog_run(_parms.timeout)
    
    def backward(self, _parms: servoParameters)->bool:
        try:
            pass                   # Implement  backward logic here
        except Exception as e:
            print(f'Error in go2pos: {e}')
            return False
        with self.__op_lock:
            self.__current_op = servoMotor.opType.backward   # Update current operation
        self._watch_dog_run(_parms.timeout)
    
    def stop(self)->bool:                               # atomic stop operation (no watchdog)
        self.__wd_stop.set()                      # Signal watchdog thread to stop
 

    def  _watch_dog_run(self, timeout:float=None)->threading.Thread:
        self.__start_time = time.time()                 # Record start time of operation
        print(f'Running whatch dog thread')         
        self.__wd = threading.Thread(target=self.__watch_dog_thread , args=(timeout,), daemon=True)
                                                        # Start watchdog thread
        self.__wd.start()   
        return self.__wd
    
    def __watch_dog_thread(self, timeout:float=None):
        print(f'Watch dog thread started')
        _status = True
        try:
            while not self.__wd_stop.is_set():
                pass                                # Monitor operation status
                if timeout is not None:
                    if (time.time() - self.__start_time) > timeout:
                        print(f'Operation timed out')
                        _status = False
                        break
                time.sleep(0.1)
            pass                                # stop operation
            print(f'Watch dog thread stopped')
        except Exception as e:
            print(f'Error in watch dog thread: {e}')
            _status = False

        self.__wd_stop.clear()
        with self.__op_lock:    
            self.__current_op = servoMotor.opType.stoped         # Update current operation

        self.devNotificationQ.put(_status)          # Notify operation completion
