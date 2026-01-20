import random
import serial.tools.list_ports
import serial
import threading    
import time

from common_utils import print_err, print_DEBUG, print_warn, print_log, exptTrace, print_trace, \
                        print_call_stack

class WLCscale:  
    _scales:list[str]      # Class variable to hold available scales
    @staticmethod
    def listScales()->list[str]:       # List available serial scales COM ports

        WLCscale._scales = list()
        ports = serial.tools.list_ports.comports()
        print_log(f'Scanning available serial ports for scales....{len(ports)} ports found: {ports}')
        for port in ports:

            print_log(f"Found port: {port.device},name={port.name}, Description: {port.description}, name={port.name}, hwid={port.hwid}, vid={port.vid}, serial_number={port.serial_number}, location={port.location}, manufacturer={port.manufacturer},product={port.product}, interface={port.interface} ")
            # if "Scale" in port.description:  # Replace with actual identifier for scales
            if port.vid == 1155:  # Vendor ID for scales
                WLCscale._scales.append(port.device)
        return  WLCscale._scales
    
    def __init__(self, serial_port: str, poll_interval: float = 0.1):
        self.__serial_port = serial_port
        self.__connection = None
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__current_weight:float = 0.0                     # Current weight reading
        self.__poll_interval = poll_interval
    
    def update_serial_port(self, serial_port: str):
        print_log(f'Updating serial port to {self.__serial_port}-> {serial_port}')
        if serial_port != self.__serial_port:
            if self.is_connected():
                self.disconnect()
            self.__serial_port = serial_port
            self.connect()

    def updatePollInterval(self, poll_interval: float):
        print_log(f'Updating poll interval to {self.__poll_interval}-> {poll_interval}')
        self.__poll_interval = poll_interval

    def connect(self)->bool:
        try:

            self.__connection = serial.Serial(self.__serial_port, 
                                            baudrate=9600, 
                                            bytesize=serial.EIGHTBITS,
                                            parity=serial.PARITY_NONE,
                                            stopbits=serial.STOPBITS_ONE,
                                            timeout=1)
            print_log(f'Connected to scale on {self.__serial_port}')
            # Start watchdog thread
            wd_thread = threading.Thread(target=self.__watch_dog_thread, daemon=True)   
            self.__wd_stop.clear()
            wd_thread.start()       
            
            return True
        except Exception as e:
            print_err(f'Error connecting to scale on {self.__serial_port}: {e}')
            exptTrace(e)
            self.__connection = None
            return False
        
    def is_connected(self)->bool:
        return self.__connection is not None and self.__connection.is_open
    
    def read_weight(self)->float:   
        try:
            if self.__connection and self.__connection.is_open:
                # self.__connection.write(b'READ\n')  # Command to read weight; replace with actual command
                self.__connection.reset_input_buffer()
                line = self.__connection.readline().decode('utf-8').strip()  # twice read to get fresh data 
                                                                            # (in case of string was partially read)
                line = self.__connection.readline().decode('utf-8').strip()
                sign:int = -1 if line[5] == '-' else 1
                weight:float = sign * float(line[6:15])
                return weight
            else:
                print_log('Scale not connected')
                return 0.0
        except Exception as e:
            print_err(f'Error reading weight: {e}')
            exptTrace(e)
            return 0.0

    def disconnect(self)->bool:
        try:
            self.__wd_stop.set()
            if self.__connection and self.__connection.is_open:
                print_log('Disconnecting from scale...')
                self.__connection.close()
            return True
        except Exception as e:
            print_err(f'Error disconnecting from scale: {e}')
            exptTrace(e)
            return False
        
    def __watch_dog_thread(self):
        
        try:
            while not self.__wd_stop.is_set():
                self.__current_weight = self.read_weight()  
                pass                                # Monitor operation status
                                

                if self.__wd_stop.wait(float(self.__poll_interval)):
                    break
                # time.sleep(self.__poll_interval)
        except Exception as e:
            print_err(f'Error in watch dog thread: {e}')
            exptTrace(e)


    def __del__(self):
        self.disconnect()   



    @property
    def weight(self):
        return self.__current_weight    


# =====  UNITEST  =====
# ===== Stub code for testing WLCscale class =====
class WLCscaleStub:
    @staticmethod
    def listScales()->list[str]:       # List available serial scales COM ports
        return  ["COM3", "COM4"]
    
    def __init__(self, serial_port: str, poll_interval: float = 0.1):
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__test_weight =random.randint(200, 9500)/100.0
        self.__poll_interval = poll_interval
        self.__serial_port = serial_port

    def read_weight(self)->float:
        # Simulate weight reading with random value and
        sign = -1 if random.randint(0,1) == 0 else 1
        self.__test_weight +=  random.randint(200, 500)/100.0*sign
        self.__test_weight = max(0.0, self.__test_weight)  # Ensure weight doesn't go below 0
        return self.__test_weight
    
    def update_serial_port(self, serial_port: str):
        print_log(f'Updating serial port to {self.__serial_port}-> {serial_port}')

    def updatePollInterval(self, poll_interval: float):
        print_log(f'Updating poll interval to {self.__poll_interval}-> {poll_interval}')

    def connect(self)->bool:
        print_log(f'Simulated connection to scale on {self.__serial_port}')
        wd_thread = threading.Thread(target=self.__watch_dog_thread, daemon=True)   
        wd_thread.start()   
        return True
    def disconnect(self)->bool:
        self.__wd_stop.set()
        print_log(f'Simulated disconnection from scale on {self.__serial_port}')
        return True
    
    def is_connected(self)->bool:
        return True
    
    def __watch_dog_thread(self):
        self.__wd_stop.clear()
        try:
            while not self.__wd_stop.is_set():
                self.__test_weight = self.read_weight()  
                pass                                # Monitor operation status
                                
                time.sleep(self.__poll_interval)
        except Exception as e:
            print_err(f'Error in watch dog thread: {e}')
            exptTrace(e)

    def __del__(self):
        self.disconnect()   

    @property
    def weight(self):
        return self.read_weight()
    
#  =====  UNITEST  =====

if __name__ == "__main__":
    from datetime import datetime, date
    try:
        scales = WLCscale.listScales()
        print_log(f"Available scales: {scales}")
        if scales:
            scale = WLCscale(scales[0])
            if scale.connect():
                while True:
                    weight = scale.read_weight()
                    print_log(f"[{datetime.now().time() }] Weight: {weight} g,  ")
                    time.sleep(1)

            else:
                print_log("Failed to connect to scale.")
    except KeyboardInterrupt:
        print_log("Interrupted by user.")

    except Exception as ex:
        import sys, traceback
        e_type, e_value, e_traceback = sys.exc_info()
        e_filename = e_traceback.tb_frame.f_code.co_filename
        e_line_number = e_traceback.tb_lineno
        print_err(f"Exception: {ex}:  type={e_type}, file={e_filename}, line={e_line_number} ")     
        exptTrace(ex)

    scale.disconnect()
