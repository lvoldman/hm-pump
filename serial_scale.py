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
        print(f'Scanning available serial ports for scales....{len(ports)} ports found: {ports}')
        for port in ports:

            print(f"Found port: {port.device},name={port.name}, Description: {port.description}, name={port.name}, hwid={port.hwid}, vid={port.vid}, serial_number={port.serial_number}, location={port.location}, manufacturer={port.manufacturer},product={port.product}, interface={port.interface} ")
            # if "Scale" in port.description:  # Replace with actual identifier for scales
            if port.vid == 1155:  # Vendor ID for scales
                serialScale._scales.append(port.device)
        return  serialScale._scales
    
    def __init__(self, serial_port: str, poll_interval: float = 0.1):
        self.serial_port = serial_port
        self.connection = None
        self.__wd_stop:threading.Event = threading.Event() # Event to stop watchdog thread
        self.__current_weight:float = 0.0                     # Current weight reading
        self.__poll_interval = poll_interval
    
    def updqate_serial_port(self, serial_port: str):
        self.serial_port = serial_port

    def update_poll_interval(self, poll_interval: float):
        self.__poll_interval = poll_interval

    def connect(self)->bool:
        try:

            self.connection = serial.Serial(self.serial_port, 
                                            baudrate=9600, 
                                            bytesize=serial.EIGHTBITS,
                                            parity=serial.PARITY_NONE,
                                            stopbits=serial.STOPBITS_ONE,
                                            timeout=1)
            print(f'Connected to scale on {self.serial_port}')
            # Start watchdog thread
            wd_thread = threading.Thread(target=self.__watch_dog_thread, daemon=True)   
            self.__wd_stop.clear()
            wd_thread.start()       
            
            return True
        except Exception as e:
            print(f'Error connecting to scale on {self.serial_port}: {e}')
            self.connection = None
            return False
    
    def read_weight(self)->float:   
        try:
            if self.connection and self.connection.is_open:
                # self.connection.write(b'READ\n')  # Command to read weight; replace with actual command
                self.connection.reset_input_buffer()
                line = self.connection.readline().decode('utf-8').strip()  # twice read to get fresh data 
                                                                            # (in case of string was partially read)
                line = self.connection.readline().decode('utf-8').strip()
                sign:int = -1 if line[5] == '-' else 1
                weight:float = sign * float(line[6:15])
                return weight
            else:
                print('Scale not connected')
                return 0.0
        except Exception as e:
            print(f'Error reading weight: {e}')
            return 0.0

    def disconnect(self)->bool:
        try:
            self.__wd_stop.set()
            if self.connection and self.connection.is_open:
                print('Disconnecting from scale...')
                self.connection.close()
            return True
        except Exception as e:
            print(f'Error disconnecting from scale: {e}')
            return False
        
    def __watch_dog_thread(self):
        
        try:
            while not self.__wd_stop.is_set():
                self.__current_weight = self.read_weight()  
                pass                                # Monitor operation status
                                
                time.sleep(self.__poll_interval)
        except Exception as e:
            print(f'Error in watch dog thread: {e}')


    def __del__(self):
        self.disconnect()   



    @property
    def weight(self):
        return self.__current_weight    


# =====  UNITEST  =====
if __name__ == "__main__":
    from datetime import datetime, date
    try:
        scales = serialScale.listScales()
        print(f"Available scales: {scales}")
        if scales:
            scale = serialScale(scales[0])
            if scale.connect():
                while True:
                    weight = scale.read_weight()
                    print(f"[{datetime.now().time() }] Weight: {weight} g,  ")
                    time.sleep(1)

            else:
                print("Failed to connect to scale.")
    except KeyboardInterrupt:
        print("Interrupted by user.")

    except Exception as ex:
        import sys, traceback
        e_type, e_value, e_traceback = sys.exc_info()
        e_filename = e_traceback.tb_frame.f_code.co_filename
        e_line_number = e_traceback.tb_lineno
        print(f"Exception: {ex}:  type={e_type}, file={e_filename}, line={e_line_number} ")     

    scale.disconnect()
