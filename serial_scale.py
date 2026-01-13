import serial.tools.list_ports
import serial
import threading    
import time

class serialScale:  
    _scales:list[str]      # Class variable to hold available scales
    @staticmethod
    def listScales()->list[str]:       # List available serial scales COM ports

        serialScale._scales = list()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "Scale" in port.description:  # Replace with actual identifier for scales
                serialScale._scales.append(port.device)
        return  serialScale._scales
    
    def __init__(self, serial_port: str, poll_interval: float = 0.1):
        self.serial_port = serial_port
        self.connection = None
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__current_weight:float = 0.0                     # Current weight reading
        self.__wd_stop.clear()
        self.__poll_interval = poll_interval
    
    def connect(self)->bool:
        try:
            self.connection = serial.Serial(self.serial_port, baudrate=9600, timeout=1)
            return True
        except Exception as e:
            print(f'Error connecting to scale on {self.serial_port}: {e}')
            self.connection = None
            return False
    
    def read_weight(self)->float:   
        try:
            if self.connection and self.connection.is_open:
                self.connection.write(b'READ\n')  # Command to read weight; replace with actual command
                line = self.connection.readline().decode('utf-8').strip()
                return float(line)
            else:
                print('Scale not connected')
                return 0.0
        except Exception as e:
            print(f'Error reading weight: {e}')
            return 0.0

    def disconnect(self)->bool:
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
            return True
        except Exception as e:
            print(f'Error disconnecting from scale: {e}')
            return False
        
    def __watch_dog_thread(self):
        
        try:
            while not self.__wd_stop.is_set():
                self.__current_weight = float(self.connection.readline().decode('utf-8').strip())   
                pass                                # Monitor operation status
                                
                time.sleep(self.__poll_interval)
        except Exception as e:
            print(f'Error in watch dog thread: {e}')

    @property
    def weight(self):
        return self.__current_weight    
