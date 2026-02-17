
import atexit
from re import T
import PySimpleGUI as sg
import logging, datetime, sys, os, re
from dataclasses import dataclass
from queue import Queue 
from collections import namedtuple
import  unidecode, struct

from rich.logging import RichHandler
from rich.console import Console
# rich_console = Console(stderr=False)

import inspect

uTranslate = lambda _str: logging.debug(unidecode.unidecode(_str))


logFileDate = datetime.datetime.now().strftime(f"LOG_%Y_%m_%d_%H_%M.txt")
log_format = u'%(asctime)s [%(levelname)s]: %(filename)s--%(funcName)s/%(lineno)d -- %(thread)d [%(threadName)s] %(message)s' 


class InstantFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(format=log_format, handlers=[
            RichHandler(
                rich_tracebacks=True,         # nice rich tracebacks in the log
                # markup=True,                  # allows using rich markup in messages
                markup=False,                  # Rich fails interpret list with [] symbols in right way :-(
                show_path=False,              # removes long file path (usually not needed)
                console=Console(stderr=False),           # can be omitted - defaults to stdout
            ),
                # logging.FileHandler(logFileDate, mode="w", encoding = 'utf-8')
                InstantFileHandler(logFileDate, mode="w", encoding = 'utf-8')
            ],
        encoding = "utf8", level=logging.DEBUG)



void_f = lambda a : None



def logCleanup():                   # log cleanup at exit
    print_log(f"Log cleanup")
    logging.shutdown()              # shutdown logging system

atexit.register(logCleanup)     # register log cleanup at exit

print_DEBUG = logging.debug
print_log = logging.info
print_warn = logging.warning
print_err = logging.error
print_trace = logging.exception

set_parm = lambda devName, parms, parName:  parms[devName][parName] if ((devName in parms.keys()) and (parName in parms[devName].keys()))   \
      else ( parms['DEAFULT'][parName] if parName in parms['DEAFULT'].keys() else None)

get_parm = lambda devName, parms, parName:  parms[devName][parName] if ((devName in parms.keys()) and (parName in parms[devName].keys()))   \
      else ( parms['DEAFULT'][parName] if parName in parms['DEAFULT'].keys() else None)



# nonNullV = lambda obj, key: key if obj else None

event2GUIFields = ["event", "value", "device"]
event2GUI = namedtuple("event2GUI", event2GUIFields, defaults=[None,] * len(event2GUIFields))


@dataclass
class globalEventQ:
    # devNotificationQ = Queue()
    stepNotificationQ = Queue()

unsigned_32 = lambda signed_int : signed_int if signed_int >= 0 else signed_int + (1 << 32)
unsigned_16 = lambda signed_int : signed_int if signed_int >= 0 else signed_int + (1 << 16)

def assign_type_parm(devName:str, parms:dict, parName:str, _type:type = str, _default=None):
    _val = get_parm(devName, parms, parName)
    if _val is not None:
        if not isinstance(_val, _type):
            print_err(f'Wrong {parName} value {_val} for type {_type}. Set value as default {_default}')
            _val = _default
    return _val if _val is not None else _default

def assign_parm(devName:str, parms:dict, parName:str, _default=None):
    _val = get_parm(devName, parms, parName)
    return _val if _val is not None else _default

def s16(value) -> int:              # convert unsigned 16 bit value to signed 16 bit value
    return -(value & 0x8000) | (value & 0x7fff)

def s32(value)-> int: 
    return -(value & 0x80000000) | (value & 0x7fffffff)

def num2binstr(num):
    bStr = format(num, 'b')
    bStr = '0'*(32-len(bStr)) + bStr
    res_str = bStr[-4:]
    for ind in range(round(len(bStr)/4) - 1):
        tmp_str = bStr[(-4)*(ind+2):(-4)*(ind+1)]
        if ind % 2:
            tmp_str = tmp_str + " " 
        else:
            tmp_str = tmp_str + "."
        
        tmp_str = tmp_str + res_str
        res_str = tmp_str

    return res_str

def toInt(num):
    try:
        res = int(num)
        return res
    except Exception as ex:
        print_err(f'-ERROR - {num} cant be conevred into integer. Using zero')
        return 0

def exptTrace(ex):
    e_type, e_object, e_traceback = sys.exc_info()
    e_filename = os.path.split(e_traceback.tb_frame.f_code.co_filename )[1]
    e_message = str(ex)
    e_line_number = e_traceback.tb_lineno
    print_err(f"Exception: {ex}:  type={e_type}, file={e_filename}, line={e_line_number} ({e_message}) ")
    return e_type, e_filename, e_line_number, e_message


def real_num_validator (str, positive = False):

    if not positive:
        int_nu = re.compile(r'-?\d+(\.\d+)?$') 
    else:
        int_nu = re.compile(r'\d+(\.\d+)?$')  
    if not int_nu.match(str):
        return False
    
    return True

def int_num_validator (str, positive = False):
    
    if not positive:
        int_nu = re.compile(r'-?\d+$')
    else:
        int_nu = re.compile(r'\d+$')
    if not int_nu.match(str):
        return False
    return True


def real_validator (str, positive = False):
    if not positive:
        int_nu = re.compile(r'-?(\d+(\.\d*)?){0,1}$') 
    else:
        int_nu = re.compile(r'(\d+(\.\d*)?){0,1}$') 
    if not int_nu.match(str):
        return False
    
    return True
    
    

def int_validator (_str, positive = False):
    if not positive:
        int_nu = re.compile(r'-?\d*$')
    else:
        int_nu = re.compile(r'\d*$')
    if not int_nu.match(_str):
        return False
    return True

def file_name_validator(_str):
    fn = re.compile(r'^[a-zA-Z0-9-_]+\.{0,1}[A-Za-z]{0,4}$')
    return True if fn.match(_str) else False

def non_empty_string_validator(_str):
    fn = re.compile(r'^\S+$')
    return True if fn.match(_str) else False

def CDAB_converter(_f_num:float) -> float:
    a = _f_num
    b = (a >> 8) & 0x000000FF | (a << 8)  & 0x0000FF00 | (a >> 8) & 0x00FF0000 | (a << 8) & 0xFF000000
    b_h = hex(b)[2:]
    b_h = '0'*(8-len(b_h)) + b_h
    b_b = bytes.fromhex(b_h)
    b_f = struct.unpack('<f', b_b)
    return b_f[0]


def DCBA_converter(_f_num:float) -> float:              # Float - Little Endian (DCBA)	
    b = _f_num
    b_h = hex(b)[2:]
    b_h = '0'*(8-len(b_h)) + b_h
    b_b = bytes.fromhex(b_h)
    b_f = struct.unpack('<f', b_b)
    return b_f[0]    



@staticmethod
class smartLocker:                              # Mutex mechanism
    def __init__(self, lock):
        self.lock = lock
        if  self.lock:
            self.lock.acquire()
    def __del__(self): 
        if  self.lock and self.lock.locked():
            self.lock.release() 

    def release(self):
        if  self.lock and self.lock.locked():
            self.lock.release() 


def clearQ(_Q:Queue):
    iCount = 0
    while not _Q.empty():
        _Q.get()
        iCount += 1
    if iCount > 0:
        print_log(f'Queue had {iCount} unproceeded messages')


def removeElementQ(_Q:Queue, element) -> bool:
    _element = None
    for _iter in _Q.queue: 
        if _iter == element:
            _element = _iter
            break
	
    if _element:
        _Q.queue.remove(_element)
        return True
    else:
        return False
	

def str2ip(_str:str) -> tuple:
    if _str is None:
        return 0, 0
    
    _str = re.sub(r"\s+", "", _str)                 # remove spaces
    return tuple(map(str, _str.split(':')))


def print_call_stack(levels=6):
    print_DEBUG(f"\nStack of ({levels} levels back):")
    for i, frame_info in enumerate(inspect.stack()[1:levels+1], 1):
        func_name = frame_info.function
        file_name = frame_info.filename
        line_no   = frame_info.lineno
        print_DEBUG(f"  {i:2d}) {func_name:20}  ←  {file_name}:{line_no}")
    
# def SetLED(window:sg.Window, key:str, color:str):
#     graph = window[key]
#     graph.erase()
#     graph.draw_circle((0, 0), 12, fill_color=color, line_color=color)


#=========================== block  __name__ == "__main__" ================
if __name__ == "__main__":
    unsigned_int = unsigned_16
    while(True):
        try:
            # val = input("Enter int: ")
            # print(f'unsign val = {val}/{hex(int(val))}/{int(val)}/{unsigned_int(int(val))}/0x{unsigned_int(int(val)):04x}/{hex(unsigned_int(int(val)))}')
            # print(f'sign val: 4 bytes {s32(int(val))} / 2 bytes {s16(int(val))}')

            _val = input("Enter hex: ")
            _fl = CDAB_converter(int(_val, 16))
            _fl_DCBA = DCBA_converter(int(_val, 16))
            print(f'val = {_val}, CDAB = {_fl} // DCBA ={_fl_DCBA}')


        except Exception as ex:
            exptTrace(ex)
            print(f'Something goes wrong input. Exception = {ex}')
            continue

        except KeyboardInterrupt as ex:

            print(f'Exiting by ^C \n{ex}')
            sys.exit()
        except Exception as ex:
            exptTrace(ex)
            print(f'Exception operation error on {ex}')   
#---------------  end of block  __name__ == "__main__" -------------------
