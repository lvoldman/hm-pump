from __future__ import annotations


from curses.ascii import isdigit
from weakref import finalize
import serial as serial
import sys, os
import time
import threading
import ctypes
from threading import Lock
from collections import namedtuple

from inputimeout  import inputimeout , TimeoutOccurred
from dataclasses import dataclass
from queue import Queue 


from common_utils import print_log, print_warn, print_err, print_DEBUG, exptTrace, s16, s32, num2binstr, set_parm, get_parm, void_f, assign_parm

from typing import TYPE_CHECKING


print_DEBUG = void_f

from ctypes import *
from ctypes import wintypes
from maxon_errors import ErrTxt
import threading

typeDict={  'char': c_char,
        'char*': c_char_p,
        '__int8': c_int8,
        'BYTE': c_uint8,
        'short': c_int16,
        'WORD': c_uint16,
        'long': c_int32,
        'DWORD': c_uint32,
        'BOOL': c_int32,
        'HANDLE': POINTER(c_uint32)
        }


void_f = lambda a : None 


'''
Device Control Commands:
Command             Controlword LowByte[binary] 
Shutdown            0xxx x110 
Switch on           0xxx x111 
Switch on & 
Enable operation    0xxx 1111 
Disable voltage     0xxx xx0x 
Quick stop          0xxx x01x 
Disable operation   0xxx 0111 
Enable operation    0xxx 1111 
Fault reset         0xxx xxxx [->] 1xxx xxxx 




 Controlword  0x6040

Bit 	Description	 	        PPM 		PVM 		    HMM 		CSP 		CSV 		CST
15 	Operating mode-specific 	Endless
                                movement 	reserved		reserved 	reserved 	reserved 	reserved
14…11 	reserved
10, 9 	reserved
8 	Operating mode-specific 	Halt 		Halt 		Halt
7 	Fault reset
6   Operating mode-specific Abs / rel 		reserved 	reserved
5 	Operating mode-specific 	Change set
                                immediately reserved 	reserved
4 	Operating mode-specific 	New setpoint reserved	Homing operation
                                                        start
3 	Enable operation
2 	Quick stop
1	 Enable voltage
0 	Switched on


----------------------------------------------------------------------


Statusword   0x6041
Bit 	Description 		    PPM 		    PVM 	    HMM 		    CSP 		    CSV 		    CST
15 	Position referenced to
    home position
14 	reserved (0)
13 	Operating mode-specific 	Following
                                error 		    Not used 	Homing error 	Following error
12 	Operating mode-specific 	Setpoint
                                acknowledge 	Speed 		Homing attained
                                                                        Drive follows
                                                                        Command value	Drive follows
                                                                                        Command value
                                                                                                            Drive follows
                                                                                                            Command value
11 	Internal limit active 	    I2t, Current 	I2t, Current
                                                Max velocity 	I2t, Current    I2t, Current
                                                                                Max. speed	I2t, Current
                                                                                            Max. speed 	I2t, Current Max. speed
10 	Operating mode-specific 	Target reached	Target reached	Target reached 	reserved 	reserved 	reserved
9 	Remote
8 	reserved (0)
7 	Warning
6 	Switch on disabled
5 	Quick stop
4 	Voltage enabled (power stage on)
3 	Fault
2 	Operation enabled
1 	Switched on
0 	Ready to switch on

-------------------------------------------------------------------




'''
DEFAULT_QSTOP_DEC =  30000
MAXON_CURRENT_ACTUAL_VALUE_QUERY = (0x30D1, 0x02, 0x04 )
TARGET_VELOCITY = 0x60FF
CONTROLWORD = 0x6040
STATUSWORD = 0x6041
QUCK_STOP_DEC = 0x6085
GET_SN_CMD = (0x1018, 0x04, 0x04)
ENABLE_CMD =  (0x6040, 0x0, 0xF, 0x2)
STALL_CMD_LST =[
    (CONTROLWORD, 0x00, 0x010F, 0x2),               # bit 8 - halt
    (TARGET_VELOCITY, 0x00, 0x00000000, 0x04),      # zero speed
    ENABLE_CMD
]

QUCK_STOP_DEC_CMD = (QUCK_STOP_DEC, 0x00)

STATUS_WORD_QUERY = (STATUSWORD, 0x00, 0x02 )

DIG_INP_CNTL = 0x3142
INP_POLARITY_CTL = 0x3141
QUICK_STOP = 0x1C   # 0x1C = 28
GENERAL_PURPOSE_D = 0x13   # 0x13 = 19
DIG_INP_4_CONF = 0x04

READ_HIGH_POLARITY = [
    (INP_POLARITY_CTL, 0x1, 0x2)
]

ACTIVATE_QUICK_STOP = [
    (DIG_INP_CNTL, DIG_INP_4_CONF, QUICK_STOP, 0x2)
]

DEACTIVATE_QUICK_STOP = [
    (DIG_INP_CNTL, DIG_INP_4_CONF, GENERAL_PURPOSE_D, 0x2)
]

THERMAL_TIME_CONSTANT_WINDING = 4.69

GLOBAL_EX_LIMIT = 100
QUCK_STOP_MASK = 0b0000000000100000

IDLE_DEV_CURRENT = 1         # mA
IDLE_DEV_VELOCITY = 10
CURRENT_WAIT_TIME = 2




class MAXON_Motor: 
    portSp = namedtuple("portSp", ["device", "protocol", "interface", "port", "baudrate", "sn", "nodeid", "sensortype"])
    resultType = namedtuple("resultType", ["res", "answData", "query"])
    activated_devs = []                                     # port numbers
    protocol = None
    # devices:MAXON_Motor.portSp = None               # list of devices
    devices:list[MAXON_Motor.portSp] = None               # list of devices
    intf = None
    mxn_lock = Lock()                               # COM port access mutex 
    epos = None
    path = '.\DLL\EposCmd64.dll'                      # EPOS Command Library path
    timeout = 500
    acceleration = 3000                            # rpm/s
    deceleration = 3000                            # rpm/s


    def __init__(self, mxnDev:MAXON_Motor.portSp):
#################################  configuration parms / constants ###########################
        self.MEASUREMENT_DELAY:float = 0.25
        self.MINIMAL_OP_DURATION:float = 0.25
        self.GRIPPER_TIMEOUT:float = 10
        self.DEFAULT_CURRENT_LIMIT:int = 300
        self.DEFAULT_ROTATION_TIME:float = 5
        self.DEAFULT_VELOCITY_EV_VOLTAGE:int = 5000
        self.DevMaxSPEED:int = 15000
        self.DevOpSPEED:int = 640
        self.EX_LIMIT = GLOBAL_EX_LIMIT
        self.IDLE_DEV_CURRENT = IDLE_DEV_CURRENT
        self.IDLE_DEV_VELOCITY = IDLE_DEV_VELOCITY
        self.CURRENT_WAIT_TIME = CURRENT_WAIT_TIME
        self.ACCELERATION =  MAXON_Motor.acceleration
        self.DECELERATION = MAXON_Motor.deceleration
        self.STALL_RELEASE = True
        self.DIAMETER = 6
        self.GEAR = 64
#########################################################################
        self.keyHandle = None                                  # Open device Handle
        self.mDev_port:str = mxnDev.port                          # USB1,USB2, USB3 for USB..
        self.mDev_nodeID:int = mxnDev.nodeid                            # 1,2,3..
        self.mDev_pos:int = 0                                 #  current position 
        self.el_current_limit:int = 0                       # electrical current limit to stop 
        self.wd = None                                      # watch dog identificator
        self.mDev_SN = mxnDev.sn                                   # Serial N (0x1018:0x04)
        self.mDev_status = False                              # device status (bool) / used for succesful initiation validation
        self.__stop_motion:threading.Event = threading.Event()  # Event to stop motion thread
        self.possition_control_mode = False                 # TRUE - control possition, FALSE - don't
        self.time_control_mode = False                      # TRUE - time control
        self.new_pos = 0
        self.sensorType = mxnDev.sensortype
#------- Bad practice --------
        self.rpm:int = self.DevOpSPEED 
#------- Bad practice --------
#############  Communication ##########
        self.__keyHandle = None                         # store for not allocating new handle on each cmd
        self.__nodeID = None                            # store for not allocating new handle on each cmd   
#######################################        
        self.start_time: float = 0                                   # Start thread time
        self.success_flag = True                            # end of op flag
        self.rotationTime:float = 0                               # rotation time
        self.diameter = self.DIAMETER
        self.gear = self.GEAR
        self.devName:str = mxnDev.sn
        self.dev_lock = Lock()
        self.devNotificationQ = Queue()

        try:

            print_log(f'Starting devName = {self.devName}')
            pErrorCode=c_uint()


            self.keyHandle = MAXON_Motor.epos.VCS_OpenDevice(mxnDev.device, mxnDev.protocol, mxnDev.interface, mxnDev.port, byref(pErrorCode)) 
   
            

            MAXON_Motor.epos.VCS_SetProtocolStackSettings(self.keyHandle, c_int32(mxnDev.baudrate), c_int32(self.timeout), byref(pErrorCode)) # set baudrate


            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            
            self.__setUpCommunication()

            self.mDev_get_cur_pos()


            print_log(f'({self.devName}) Serial number = {self.mDev_SN} Possition = {self.mDev_pos}')

        except Exception as ex:

            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
   
            print_err(f"({self.devName}) ERROR. Initiating MAXON port {self.mDev_port} was lost. Unexpected Exception: {ex}")
            return                                  # no valid FAULHABBER motor can be added
        
        else:
            self.mDev_status = True
            pass

        if self.mDev_port in MAXON_Motor.activated_devs:
            print_err(f"**ERROR** . ({self.devName}) Device with port = {self.mDev_port} already activated")
        else:
            MAXON_Motor.activated_devs.append(self.mDev_port)
        



    

    def __del__(self):
        pErrorCode=c_uint()

        print_log(f'Releasing/deleting MAXON on port {self.mDev_port}')  

        self.__stop_motion.set()    

        try:

            MAXON_Motor.epos.VCS_SetDisableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode)) # disable device
            MAXON_Motor.epos.VCS_CloseDevice(self.keyHandle, byref(pErrorCode))


            print_log(f'({self.devName}) MAXON disabled on port {self.mDev_port}.')
            MAXON_Motor.activated_devs.remove(self.mDev_port)
        except  Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'({self.devName})  MAXON device on port {self.mDev_port} could not be closed. Exception: {ex} of type: {type(ex)}.')
        finally:
            pass


        if not len(MAXON_Motor.activated_devs):         # if no more active devices - deactivate
            print_log(f'No more active MAXON devices. Exiting.')
            try:
                MAXON_Motor.devices = None

                pass

            except  Exception as ex:
                e_type, e_filename, e_line_number, e_message = exptTrace(ex)
                print_err(f'ERROR.  MAXON on port {self.mDev_port} could not be closed cortrectly. Exception: {ex} of type: {type(ex)}.')
            finally:
                pass


    @staticmethod
    def getMaxBaudrate(DeviceName, ProtocolStackName, InterfaceName, PortName)->int:
        pBaudrateSel = c_int32()
        pEndOfSelection =  c_bool(False)
        pErrorCode = c_uint()

        bdRate = -1
        MAXON_Motor.epos.VCS_GetBaudrateSelection(DeviceName, ProtocolStackName, InterfaceName, PortName, True, byref(pBaudrateSel), byref(pEndOfSelection), byref(pErrorCode))
        if pErrorCode.value == 0:
            bdRate = pBaudrateSel.value
        else:
            print_err (f'ERROR reading baudrate. DeviceName = {DeviceName}, ProtocolStackName = {ProtocolStackName}, InterfaceName = {InterfaceName}, PortName = {PortName} Baudrate (1) = {pBaudrateSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        while not pEndOfSelection.value:
                MAXON_Motor.epos.VCS_GetBaudrateSelection(DeviceName, ProtocolStackName, InterfaceName, PortName, False, byref(pBaudrateSel), byref(pEndOfSelection), byref(pErrorCode))
                if pErrorCode.value == 0:
                    bdRate = pBaudrateSel.value
                else:
                    print_err (f'RROR reading baudrate. DeviceName = {DeviceName}, ProtocolStackName = {ProtocolStackName}, InterfaceName = {InterfaceName}, PortName = {PortName}  Baudrate ...  = {pBaudrateSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    break
        print_log(f'Max baudrate = {bdRate}')
        return bdRate


    @staticmethod
    def getAvailablePorts(DeviceName, ProtocolStackName, InterfaceID)->list:
        MaxStrSize = 100
        pEndOfSelection =  c_bool(False)
        pErrorCode = c_uint()

        # InterfaceName = c_char_p(b'USB')
        InterfaceName = InterfaceID
        pPortSel = create_string_buffer(MaxStrSize)
        localPortlst = list()
        MAXON_Motor.epos.VCS_GetPortNameSelection(DeviceName, ProtocolStackName, InterfaceName, True, byref(pPortSel), MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
        if pErrorCode.value == 0:
            bdRate = MAXON_Motor.getMaxBaudrate(DeviceName, ProtocolStackName, InterfaceName, pPortSel.value)
            SN, nodeID, senorType = MAXON_Motor.getDevSN(DeviceName, ProtocolStackName, InterfaceName, pPortSel.value)

            localPortlst.append(pPortSel.value)
            MAXON_Motor.devices.append(MAXON_Motor.portSp(device=DeviceName, protocol=ProtocolStackName, interface=InterfaceName, port=pPortSel.value, baudrate=bdRate, sn=SN, nodeid=nodeID, sensortype=senorType))
        else:
            print_err (f'ERROR getting port. Dev = {DeviceName} Protocol = {ProtocolStackName} InterfaceName = {InterfaceName} Port (1) = {pPortSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

        while not pEndOfSelection.value:
            MAXON_Motor.epos.VCS_GetPortNameSelection(DeviceName, ProtocolStackName, InterfaceName, False, byref(pPortSel), MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
            if pErrorCode.value == 0:
                bdRate = MAXON_Motor.getMaxBaudrate(DeviceName, ProtocolStackName, InterfaceName, pPortSel.value)
                SN, nodeID, senorType = MAXON_Motor.getDevSN(DeviceName, ProtocolStackName, InterfaceName, pPortSel.value)
                
                localPortlst.append(pPortSel.value)
                MAXON_Motor.devices.append(MAXON_Motor.portSp(device=DeviceName, protocol=ProtocolStackName, interface=InterfaceName, port=pPortSel.value, baudrate=bdRate, sn=SN, nodeid=nodeID, sensortype=senorType))
            else:
                print_err (f'ERROR getting port. Dev = {DeviceName} Protocol = {ProtocolStackName} InterfaceName = {InterfaceID} Port ... = {pPortSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                break


        return localPortlst


    @staticmethod
    def getAvailableInterfaces(DeviceName, ProtocolStackName)->list: 
        MaxStrSize = 100
        pEndOfSelection =  c_bool(False)
        pErrorCode = c_uint()

        pInterfaceNameSel = create_string_buffer(MaxStrSize)
        InterfaceLst = list()
        MAXON_Motor.epos.VCS_GetInterfaceNameSelection(DeviceName, ProtocolStackName, True, byref(pInterfaceNameSel), \
                                                       MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
        if pErrorCode.value == 0:
            InterfaceLst.append(pInterfaceNameSel.value)
        else:
            print_err (f'ERROR getting interface. Dev = {DeviceName} Protocol = {ProtocolStackName} InterfaceName (1) = {pInterfaceNameSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

        while not pEndOfSelection.value:
            MAXON_Motor.epos.VCS_GetInterfaceNameSelection(DeviceName, ProtocolStackName, False, byref(pInterfaceNameSel), \
                                                           MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
            if pErrorCode.value == 0:
                InterfaceLst.append(pInterfaceNameSel.value)
            else:
                print_err (f'ERROR getting interface. Dev = {DeviceName} Protocol = {ProtocolStackName} InterfaceName ... = {pInterfaceNameSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                break

        return InterfaceLst


    @staticmethod
    def getAvailableProtocols(DeviceName)->list:
        MaxStrSize = 100
        pEndOfSelection =  c_bool(False)
        pErrorCode = c_uint()

        pProtocolStackNameSel = create_string_buffer(MaxStrSize)
        protLst = list()
        MAXON_Motor.epos.VCS_GetProtocolStackNameSelection(DeviceName, True, byref(pProtocolStackNameSel), MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
        if pErrorCode.value == 0: 
            protLst.append(pProtocolStackNameSel.value)
        else:
            print_err (f'ERROR getting protocol. Dev = {DeviceName} Protocol (1) = {pProtocolStackNameSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        while not pEndOfSelection.value:
            MAXON_Motor.epos.VCS_GetProtocolStackNameSelection(DeviceName, False, byref(pProtocolStackNameSel), MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
            if pErrorCode.value == 0:
                protLst.append(pProtocolStackNameSel.value)
            else:
                print_err (f'ERROR getting protocol. Dev = {DeviceName} Protocol ... = {pProtocolStackNameSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode = 0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                break

        return protLst

    @staticmethod
    def getAvailableDevices()->list:
        MaxStrSize = 100
        pDeviceNameSel = create_string_buffer(MaxStrSize)
        pEndOfSelection =  c_bool(False)
        pErrorCode = c_uint()

        devList = list()
        MAXON_Motor.epos.VCS_GetDeviceNameSelection(True, byref(pDeviceNameSel),  MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
        if pErrorCode.value == 0:
            devList.append(pDeviceNameSel.value)
        else:
            print_err (f'ERROR getting device. Device (1) = {pDeviceNameSel.value}  , pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        while not pEndOfSelection.value:
            MAXON_Motor.epos.VCS_GetDeviceNameSelection(False, byref(pDeviceNameSel),  MaxStrSize, byref(pEndOfSelection), byref(pErrorCode))
            if pErrorCode.value == 0:
                devList.append(pDeviceNameSel.value)
            else:
                print_err (f'ERROR getting device. Device ... = {pDeviceNameSel.value}, pEndOfSelection = {pEndOfSelection.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                break

        return devList


    @staticmethod
    def getDevSN(DeviceName, ProtocolStackName, InterfaceName, portU):    
                                     #Stupid MAXON stuff. The dialog windows
                                     # appears/disappears to get the S/N, 
                                     # otherwise device should be opened and initiated to get the S/N
        MaxStrSize = 100

        pErrorCode = c_uint()

        pTimeout = c_int32()
        pNodeId = c_int32()

        pKeyHandle = c_void_p()
        pBaudrateSel = c_int32()


        MAXON_Motor.epos.VCS_FindDeviceCommunicationSettings(
                                                byref(pKeyHandle), DeviceName, ProtocolStackName, InterfaceName, portU,
                                                MaxStrSize, byref(pBaudrateSel), byref(pTimeout),   
                                                byref(pNodeId), 3, byref(pErrorCode)
                                                )
        
        if pErrorCode.value != 0:
            print_log(f'ERROR. No device found for device = {DeviceName}, Protocol = {ProtocolStackName}, Interface = {InterfaceName}, Port = {portU}, \
                pBaudrateSel = {pBaudrateSel.value}, Timeout = {pTimeout.value},\
                pNodeId = {pNodeId.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            return 0, 0, 0



        pSensorType = c_int32()

        MAXON_Motor.epos.VCS_GetSensorType(pKeyHandle.value, pNodeId.value, byref(pSensorType), byref(pErrorCode))

        if not pErrorCode.value == 0:
            print(f'ERROR getting Sendor Type : pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            return 0, pNodeId.value, 0

        pData = c_int32()
        pNbOfBytesRead =  c_int32()
        MAXON_Motor.epos.VCS_GetObject(pKeyHandle.value, pNodeId.value, GET_SN_CMD[0], GET_SN_CMD[1], byref(pData), \
                                       GET_SN_CMD[2], byref(pNbOfBytesRead), byref(pErrorCode))

        if pErrorCode.value == 0:
            return pData.value, pNodeId.value, pSensorType.value
        else:
            print(f'ERROR reading Serial # = {pData.value} pNbOfBytesRead = {pNbOfBytesRead.value} pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            return 0, pNodeId.value, pSensorType.value



    @staticmethod
    def enum_devs(mxnDevice, mxnInterface):

        MAXON_Motor.devices = list()
        try:   
            devList = MAXON_Motor.getAvailableDevices()
            print_log(f'-> Device List = {devList}')

            for devID in devList:
                if devID == mxnDevice:
                    protLst = MAXON_Motor.getAvailableProtocols(devID)
                else:
                    continue

                print_log(f'->[{devID}]-> Protocol List = {protLst}')

                for protID in protLst:
                    InterfaceLst = MAXON_Motor.getAvailableInterfaces(devID, protID)
                    print_log(f'->[{devID}]->[{protID}]-> Inteface List = {InterfaceLst}')

                    for InterfaceID in InterfaceLst:
                        if InterfaceID == mxnInterface:
                            localPortlst = MAXON_Motor.getAvailablePorts(devID, protID, InterfaceID)
                        else:
                            continue
                        
                        print_log(f'->[{devID}]->[{protID}]->[{InterfaceID}]-> Port List = {localPortlst}')



            print_log('---------------------------------------------------------')

            print_log(f'Found {len(MAXON_Motor.devices)} USB MAXON_Motor.devices \n{MAXON_Motor.devices}')
                        
            print_log('---------------------------------------------------------')          
          
     
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)

            print_err(f"Error enumerating MAXON devices. Exception: {ex} of type: {type(ex)}")
            MAXON_Motor.devices = None
            

        return MAXON_Motor.devices

        


    @staticmethod
    def init_devices(mxnDevice=b'EPOS4', mxnInterface=b'USB'):

        try:
            init_lock = Lock()

            cdll.LoadLibrary(MAXON_Motor.path)              # have no idea why but Maxon wants it
            MAXON_Motor.epos = CDLL(MAXON_Motor.path)
            print_log(f'Looking for maxon devices, mxnDevice = {mxnDevice}, mxnInterface = {mxnInterface}')
            MAXON_Motor.enum_devs(mxnDevice, mxnInterface)

            if len(MAXON_Motor.devices) == 0:
                print_log("No MAXON devices detected in the system")
                MAXON_Motor.devices = None
                return None
        except Exception as ex:
            exptTrace(ex)
            print_err(f"Error initiating MAXON devices. Exception: {ex} of type: {type(ex)}")
            MAXON_Motor.devices = None

        
        return MAXON_Motor.devices
            


##############################   
#  MXN_cmd() 
#
#
##############################

    @staticmethod
    # def MXN_cmd(port, arr, keyHandle=None, nodeID = None, DeviceName = None, ProtocolStackName = None, InterfaceName = None, lock = None):
    def MXN_cmd(mxnPort, arr, keyHandle=None, nodeID = None, lock = None):


        MaxStrSize = 100

        pErrorCode = c_uint()

        pTimeout = c_int32()
        pNodeId = c_int32()

        pKeyHandle = c_void_p()
        pBaudrateSel = c_int32()
        retValues = []
        

        pProtocolStackName = create_string_buffer(MaxStrSize)
        pDeviceNameSel = create_string_buffer(MaxStrSize)
        pInterfaceNameSel = create_string_buffer(MaxStrSize)



        if len(arr) == 0:
            print_err(f'Empty CMD array = {arr}')
            return retValues
        

        # sL = MAXON_Motor.smartLocker(lock)                  #  mutex for FH channel
        sL = MAXON_Motor.smartLocker(MAXON_Motor.mxn_lock)                  #  mutex for FH channel
        
        try:
            
            if keyHandle is None or nodeID is None:           # keyHandle is not available, try to resolve ot using portID    

                
                MAXON_Motor.epos.VCS_FindDeviceCommunicationSettings(
                                            byref(pKeyHandle), byref(pDeviceNameSel), byref(pProtocolStackName), 
                                            byref(pInterfaceNameSel), mxnPort,
                                            MaxStrSize, byref(pBaudrateSel), byref(pTimeout),   
                                            byref(pNodeId), 3, byref(pErrorCode)
                                            )
                
                if pErrorCode.value != 0:
                    print_log(f'ERROR. No device found for device = {pDeviceNameSel.value}, Protocol = {pProtocolStackName.value}, Interface = {pInterfaceNameSel.value}, Port = {mxnPort},\
                        pBaudrateSel = {pBaudrateSel.value}, Timeout = {pTimeout.value},\
                        pNodeId = {pNodeId.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    return retValues
                else: 
                    keyHandle = pKeyHandle.value
                    nodeID = pNodeId.value


            MAXON_Motor.epos.VCS_ClearFault(c_void_p(keyHandle) , c_uint16(nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                    print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'Exception: {ex} of type: {type(ex)} for port {mxnPort}.')
            # raise ex
            return retValues

        # print_log(f'CMD array = {arr}')
        for _cmd in arr:
            res = None
            answData = None
            try:      
                if len(_cmd) == 3:  
                    pData = c_int32()                   # Using 4 bytes buffer. to support in string replace to create_string_buffer()
                    pNbOfBytesRead =  c_int32()
                    MAXON_Motor.epos.VCS_GetObject(keyHandle, nodeID, _cmd[0], _cmd[1], byref(pData), _cmd[2], 
                                                   byref(pNbOfBytesRead), byref(pErrorCode))
                    print_DEBUG(f"VCS_GetObject({mxnPort}, 0x{_cmd[0]:04x}, 0x{_cmd[1]:04x} [{_cmd[2]} bytes]) = {pData.value} / answData=0x{pData.value:04x} ({pNbOfBytesRead.value} bytes)")
                    if pErrorCode.value == 0:
                        answData = pData.value
                    else:
                        print_err(f'ERROR reading object: {_cmd} from port {mxnPort}')
                        answData = None
                elif len(_cmd) == 4:
                    pNbOfBytesWritten = c_int32()
                    data =  c_int32(_cmd[2])

                    print_log(f"VCS_SetObject({mxnPort}, 0x{_cmd[0]:04x}, 0x{_cmd[1]:04x}, 0x{_cmd[2]:04x}, 0x{_cmd[3]:04x}) bytes will be sent ")
                    MAXON_Motor.epos.VCS_SetObject(keyHandle, nodeID, _cmd[0], _cmd[1], byref(data), _cmd[3],   \
                                                   byref(pNbOfBytesWritten),  byref(pErrorCode))
                    print_log(f"VCS_SetObject() = {pNbOfBytesWritten.value} done ")
                    
                    if pErrorCode.value != 0:
                        print_err(f'ERROR writing object: {_cmd} to port {mxnPort}')
                        
                else:
                    print_err(f'Error: Wrong command/query format: {_cmd}')
                    continue
                
                if pErrorCode.value == 0:
                    retValues.append(MAXON_Motor.resultType(res = pErrorCode, answData = answData, query=_cmd))
                else:
                    print_err(f'Error executing CMD = {_cmd} with res = 0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            except Exception as ex:
                    e_type, e_filename, e_line_number, e_message = exptTrace(ex)
                    print_err(f"Exception: {ex} of type: {type(ex)} on cmd {_cmd}")
                    continue
                ############

            
        return retValues
    
    def __setUpCommunication(self)->bool:
        MaxStrSize = 100
        pErrorCode = c_uint()
        pTimeout = c_int32()
        pNodeId = c_int32()
        pKeyHandle = c_void_p()
        pBaudrateSel = c_int32()

        pProtocolStackName = create_string_buffer(MaxStrSize)
        pDeviceNameSel = create_string_buffer(MaxStrSize)
        pInterfaceNameSel = create_string_buffer(MaxStrSize)

        
        try:
            
            if self.__keyHandle == None:           # keyHandle is not available, try to resolve ot using portID    

                
                MAXON_Motor.epos.VCS_FindDeviceCommunicationSettings(
                                            byref(pKeyHandle), byref(pDeviceNameSel), byref(pProtocolStackName), 
                                            byref(pInterfaceNameSel), self.mDev_port,
                                            MaxStrSize, byref(pBaudrateSel), byref(pTimeout),   
                                            byref(pNodeId), 3, byref(pErrorCode)
                                            )
                
                if pErrorCode.value != 0:
                    print_log(f'ERROR. No device found for device = {pDeviceNameSel.value}, Protocol = {pProtocolStackName.value}, Interface = {pInterfaceNameSel.value}, Port = {self.mDev_port},\
                        pBaudrateSel = {pBaudrateSel.value}, Timeout = {pTimeout.value},\
                        pNodeId = {pNodeId.value}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    return False
                else: 
                    self.__keyHandle = pKeyHandle.value
                    self.__nodeID = pNodeId.value


        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'Exception: {ex} of type: {type(ex)} for port {self.mDev_port}.')
            return False
        
        return True


    def init_dev(self) -> bool:
        
        pErrorCode = c_uint()
        print_log(f'Clearing  MAXON devise on port {self.mDev_port}')
        try:
            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                    print_log(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    # raise Exception(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')


            self.el_current_limit = self.DEFAULT_CURRENT_LIMIT
            

        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON initiation on port {self.mDev_port} failed. Exception: {ex} of type: {type(ex)}.')
            return False

        return True
    def mDev_get_actual_current(self) -> int:
        pCurrentIs = c_int32(0)
        pErrorCode = c_uint()

        MAXON_Motor.epos.VCS_GetCurrentIs(self.keyHandle, self.mDev_nodeID, byref(pCurrentIs), byref(pErrorCode))
        actualCurrentValue:int = s16(pCurrentIs.value)

        if pErrorCode.value != 0:
            print_err(f'Getting Actual Current Value on port  {self.mDev_port} failed. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)} ')
            return -1
        else:
            return actualCurrentValue
        

    def _is_pos_reached(self, target_pos:int, ex_limit:int) -> bool:
        pErrorCode = c_uint()
        pTargetReached = c_bool(False)
        try:
            MAXON_Motor.epos.VCS_GetMovementState(self.keyHandle, self.mDev_nodeID, byref(pTargetReached), byref(pErrorCode))

            print_DEBUG(f'MAXON: POSITION REACHED (bit 10 at statusword  )={pTargetReached.value}')
            if pErrorCode.value == 0:


                if pTargetReached.value:        # Position reached - bit 10 at statusword 
                    print_log(f'POSITION REACHED on  MAXON port {self.mDev_port}. Exiting watchdog')

                    return True
            else:
                print_err(f'MAXON failed read POSITION REACHED status on port = {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'Exception: {ex} of type: {type(ex)} on checking POSITION REACHED status for port {self.mDev_port}.')
        return False
    

    
        
    def  mDev_watch_dog_thread(self):
        
        print_log (f'>>> WatchDog MAXON  started on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}')
        time.sleep(self.MEASUREMENT_DELAY)                 # waif for a half of sec
        self.success_flag = True
        self.__stop_motion.clear()              # reset stop event
        self.start_time = time.time()   

        max_GRC:int = 0
        while (not self.__stop_motion.is_set()):
            try:
                pCurrentIs = c_int32(0)
                pErrorCode = c_uint()
                pTargetReached = c_bool(False)
                pQuickStop = c_bool(False)
                pState = c_uint()
                pVelocityIs = c_long()

#------------------------
                # MAXON_Motor.epos.VCS_GetCurrentIs(self.keyHandle, self.mDev_nodeID, byref(pCurrentIs), byref(pErrorCode))
                # actualCurrentValue:int = s16(pCurrentIs.value)
                actualCurrentValue:int = self.mDev_get_actual_current()
#------------------------

                print_DEBUG(f'WatchDog MAXHON Actual Current Value = {actualCurrentValue}')
                if pErrorCode.value == 0:
                   
                    max_GRC = abs(actualCurrentValue) if abs(actualCurrentValue) > max_GRC else max_GRC

                    if (int(abs(actualCurrentValue)) > int(self.el_current_limit)):
                        print_log(f' WatchDog MAXON: Actual Current Value = {actualCurrentValue}, Limit = {self.el_current_limit}')
                        _pos = self.mDev_get_cur_pos()
                        if abs(_pos - self.new_pos) > self.EX_LIMIT:
                            print_log(f'Desired position [{self.new_pos}] is not reached. Current position = {_pos}')
                            self.success_flag = False
                        break


                else:
                    print_err(f'WatchDog MAXON failed get Actual Current Value on port  {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)} ')


                

                if self.time_control_mode:
                    end_time = time.time()
                    if end_time - self.start_time > self.rotationTime:
                        print_log(f' WatchDog MAXON: TIME/DIST ROTATOR operation completed, port = {self.mDev_port}, actual current value = {actualCurrentValue}, Limit = {self.el_current_limit}, max GRC = {max_GRC} ')
                        break

               
                MAXON_Motor.epos.VCS_GetQuickStopState(self.keyHandle, self.mDev_nodeID, byref(pQuickStop), byref(pErrorCode))

                print_DEBUG(f'WatchDog MAXON: QuickStop status ={pQuickStop.value}')
                if pErrorCode.value == 0:
                    _status:int = 0
                    _qStop:bool =  False

############
                    _statusWord = MAXON_Motor.MXN_cmd(self.mDev_port, [STATUS_WORD_QUERY], keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock=MAXON_Motor.mxn_lock)
                    if len(_statusWord) > 0:
                        _status  = _statusWord[0].answData
                        # _qStop:bool = bool(_status & 0x10)
                        _qStop = ((_status & 0x0f) == 0b0111) and (((_status >> 5) & 0x03) == 0b00) 
                                                            # quick stop : xxxx xxxx x00x 0111
                    
                    if not (_qStop == bool(pQuickStop.value)):
                        print_err(f'WARNING!!!! _qStop = {_qStop}(status =  0x{_status}:02x <> {num2binstr(_status)}) //  pQuickStop.value = { pQuickStop.value} ')

                    MAXON_Motor.epos.VCS_GetVelocityIs(self.keyHandle, self.mDev_nodeID, byref(pVelocityIs), byref(pErrorCode))

                    MAXON_Motor.epos.VCS_GetState(self.keyHandle, self.mDev_nodeID, byref(pState), byref(pErrorCode))
                    _qStop_state:bool = (pState.value == 0x0002)                 # QuickStop state
###########                            
                    
                    if pQuickStop.value or _qStop or _qStop_state or ( (time.time() - self.start_time > self.CURRENT_WAIT_TIME)  \
                                and  ((abs(actualCurrentValue) <= self.IDLE_DEV_CURRENT) or (abs(pVelocityIs.value) <= self.IDLE_DEV_VELOCITY))):        # Quick stop is active 

                        print_log(f'MAXON entered QuickStop state at port {self.mDev_port}. Exiting watchdog')
                        print_log(f'{self.devName}: _qStop = {_qStop}(status =  0x{_status:02x} <> {num2binstr(_status)}) // state = {pState.value} (QuckStop by state = {_qStop_state}) //  pQuickStop.value = { pQuickStop.value} //  current = {actualCurrentValue}mA // velocity = {pVelocityIs.value}')

                        break
                else:
                    print_err(f'WatchDog MAXON failed read QuickStop status on port = {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                if self.possition_control_mode:

                    MAXON_Motor.epos.VCS_GetMovementState(self.keyHandle, self.mDev_nodeID, byref(pTargetReached), byref(pErrorCode))

                    print_DEBUG(f'WatchDog MAXON: POSITION REACHED (bit 10 at statusword  )={pTargetReached.value}')
                    if pErrorCode.value == 0:


                        if pTargetReached.value:        # Position reached - bit 10 at statusword 
                            print_log(f'POSITION REACHED on  MAXON port {self.mDev_port}. Exiting watchdog')

                            break
                    else:
                        print_err(f'WatchDog MAXON failed read POSITION REACHED status on port = {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            except Exception as ex:
                e_type, e_filename, e_line_number, e_message = exptTrace(ex)
                print_err(f'WatchDog MAXON failed on port = {self.mDev_port}. Exception: {ex} of type: {type(ex)}.')
                self.success_flag = False
                break
            finally:
                pass
            
        end_time = time.time()
        print_log(f' WatchDog MAXON: Start time = {self.start_time}, end time ={end_time}, delta = {end_time - self.start_time}')
        print_log (f'>>> WatchDog MAXON  completed on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}, minimal operation time = {self.MINIMAL_OP_DURATION}')
        if end_time - self.start_time - self.MEASUREMENT_DELAY < self.MINIMAL_OP_DURATION:
            print_log(f' WatchDog MAXON: Abnormal termination on port = {self.mDev_port}')
            self.success_flag = False

        time.sleep(0.1)

    
        if not self.__stop_motion.is_set():
            print_log(f'Thread is being stoped')
            self.mDev_stop()
            
        
        if self.dev_lock.locked():
            self.dev_lock.release()
        else:
            print_err(f'-WARNING unlocket mutual access mutex')


        self.mDev_get_cur_pos()
        self.devNotificationQ.put(self.success_flag)
        
        return
    

    def  mDev_watch_dog(self):
        # self.start_time = time.time()
        self.wd = threading.Thread(target=self.mDev_watch_dog_thread)
        self.wd.start()
        return self.wd

    def mDev_stop(self)-> bool:

    
        try:
            pErrorCode = c_uint()
            MAXON_Motor.epos.VCS_SetQuickStopState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            
            if self.STALL_RELEASE:
                MAXON_Motor.epos.VCS_SetDisableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                

            self.__stop_motion.set()    

            print_log(f'Motor is being disabled on port: {self.mDev_port}')
            if pErrorCode.value != 0:
                print_err(f'ERROR MAXON failed disable port = {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'ERROR MAXON failed disable port = {self.mDev_port}. Exception: {ex} of type: {type(ex)}.')
            return False
        
        self.mDev_get_cur_pos()
        return True

    def velocityModeMove(self, _velocity = None):
        pErrorCode = c_uint()
        print_log(f'Velocity Mode Movement, dev = {self.devName}, velocity = {_velocity}')
        try:
            if not (_velocity == 0):
                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, self.ACCELERATION, self.DECELERATION, byref(pErrorCode))
                if pErrorCode.value != 0:
                    print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, (-1)*_velocity, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            else:           # speed == 0
                MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
                                                                                                            
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON velocity mode movement attempt failed on port = {self.mDev_port} / dev: {self.devName}. Exception: [{ex}].')
            raise ex
    

    def currentModeMove(self, _voltage):
        pErrorCode = c_uint()
        print_log(f'Moving using current mode. Dev: {self.devName}, voltage = {_voltage}')
        try:
            MAXON_Motor.epos.VCS_ActivateCurrentMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR Activation Current Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
            MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            MAXON_Motor.epos.VCS_SetCurrentMustEx(self.keyHandle, self.mDev_nodeID, _voltage, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR: Setting Current: VCS_SetCurrentMustEx(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON current mode move failed on port = {self.mDev_port}. Exception: [{ex}].')
            raise ex


    def go2pos(self, new_position, velocity = None, acceleration = None, deceleration = None, stall=None)->bool:
        if not self.mutualControl():
            return False
        if not acceleration == None:
            self.ACCELERATION = int(acceleration)
        if not deceleration == None:
            self.DECELERATION = int(deceleration)

        self.new_pos = new_position
        if velocity == None:
            velocity = int(self.rpm)

        self.success_flag = True
        self.possition_control_mode = True
        self.time_control_mode = False 
        print_log(f'MAXON GO2POS {new_position} velocity = {velocity}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {self.ACCELERATION}, dec = {self.DECELERATION} ')
        try:
            pErrorCode = c_uint()

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            if (velocity != 0):
                MAXON_Motor.epos.VCS_ActivateProfilePositionMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetPositionProfile(self.keyHandle, self.mDev_nodeID, int(velocity), \
                                                        self.ACCELERATION, self.DECELERATION, byref(pErrorCode)) 
                if pErrorCode.value != 0:
                    print_err(f'WARNING setting Position Profile. Handle={self.keyHandle}, nodeID = {self.mDev_nodeID}, velocity = {velocity}, pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveToPosition(self.keyHandle, self.mDev_nodeID, new_position, True, True, byref(pErrorCode)) 
                print_log(f'Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, position to move = {new_position}')
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Moving to position. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            else:               # speed = 0
                MAXON_Motor.epos.VCS_HaltPositionMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting the device (speed == 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            

        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON go2pos  failed on port = {self.mDev_port}. Exception: {ex} of type: {type(ex)}.')
            self.success_flag = False
            self.mDev_stop()
            if self.dev_lock.locked():
                self.dev_lock.release()
            return False
            
            
        self.mDev_watch_dog()
        return True  

    def mDev_stall(self)->bool:


        try:
            MAXON_Motor.MXN_cmd(self.mDev_port, STALL_CMD_LST, keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock = MAXON_Motor.mxn_lock)

        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON dev failed to stall on port = {self.mDev_port}. Exception: {ex} of type: {type(ex)}.')
            return False

        self.__stop_motion.set()    


        if self.dev_lock.locked():
            self.dev_lock.release()
        
        return True


    

    def  mDev_forward(self, velocity = None, acceleration = None, deceleration = None, timeout=None, polarity:bool=None, stall = None)->bool:
        if not self.mutualControl():
            return False
        
        if not velocity == None:
            self.rpm = int(velocity)



        self.success_flag = True
        self.possition_control_mode = False
        if timeout:
            self.time_control_mode = True
            self.rotationTime = float(timeout)
        else:
            self.time_control_mode = False
        
        try:
            pErrorCode = c_uint()

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
            if self.rpm == 0:
                print_log(f'Going stall on port = {self.mDev_port}')
                MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           
            elif (self.rpm != 0):
                print_log(f'Going forward on port = {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {self.ACCELERATION}, dec = {self.DECELERATION}')

                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, self.ACCELERATION, self.DECELERATION, byref(pErrorCode))
                if pErrorCode.value != 0:
                    print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, self.rpm, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                                                                                          
        except Exception as ex:
                e_type, e_filename, e_line_number, e_message = exptTrace(ex)
                print_err(f'MAXON forward failed on port = {self.mDev_port}. Exception: [{ex}] of type: {type(ex)}.')
                self.success_flag = False
                self.mDev_stop()
                if self.dev_lock.locked():
                    self.dev_lock.release()
                return False
        
        else:
            print_log (f"MAXON forward/stall started on port = {self.mDev_port}" )
        
        if  self.rpm:                       # no need watchdog for zero speed
            self.mDev_watch_dog()
        else: 
            return self.mDev_stop()

        return True
    
    def  mDev_backward(self, velocity = None, acceleration = None, deceleration = None, timeout=None, polarity:bool=None, stall = None)->bool:

        if not self.mutualControl():
            return False
        
        if not velocity == None:
            self.rpm = int(velocity)


        self.success_flag = True
        self.possition_control_mode = False

        if timeout:
            self.time_control_mode = True
            self.rotationTime =  float(timeout)
        else:
            self.time_control_mode = False

        print_log(f'Going backward on port = {self.mDev_port}, velocity = {self.rpm}')

      
        try:
            pErrorCode = c_uint()

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
            if self.rpm == 0:
                print_log(f'Going stall on port = {self.mDev_port}')
                MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           
            elif (self.rpm != 0):
                print_log(f'Going backward on port = {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {self.ACCELERATION}, dec = {self.DECELERATION}')

                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, self.ACCELERATION, self.DECELERATION, byref(pErrorCode))
                if pErrorCode.value != 0:
                    print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, (-1)*self.rpm, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                                                                                          
        except Exception as ex:
                e_type, e_filename, e_line_number, e_message = exptTrace(ex)
                print_err(f'MAXON backward failed on port = {self.mDev_port}. Exception: [{ex}] of type: {type(ex)}.')
                self.success_flag = False
                self.mDev_stop()
                if self.dev_lock.locked():
                    self.dev_lock.release()
                return False
        else:
            print_log (f"MAXON backward/stall started on port = {self.mDev_port}" )
 

        if  self.rpm:                       # no need watchdog for zero speed
            self.mDev_watch_dog()
        else: 
            return self.mDev_stop()

        return True
    
    
    def mDev_stored_pos(self): 
        return self.mDev_pos

   
    def mDev_get_cur_pos(self) -> int:
        try:
            pPositionIs=c_long()
            pErrorCode=c_uint()
            ret = MAXON_Motor.epos.VCS_GetPositionIs(self.keyHandle, self.mDev_nodeID, byref(pPositionIs), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err (f'ERROR geting MAXON {self.devName}  position on port {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            self.mDev_pos = pPositionIs.value
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f"ERROR retriving position on device = {self.devName}, port={self.mDev_port},  Unexpected Exception: {ex}")
            return 0         
        else:
            return self.mDev_pos        

    def  mDev_reset_pos(self)->bool:
        
        self.mDev_stop()
        
        pErrorCode=c_uint()
        self.mDev_get_cur_pos()              # getting actual current position
        print_log (f"MAXON {self.devName} starting HOMING on port = {self.mDev_port} /  position = {self.mDev_pos}" ) 

        try:

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                
            MAXON_Motor.epos.VCS_ActivateHomingMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            # MAXON_Motor.epos.VCS_DefinePosition(self.keyHandle, self.mDev_nodeID, self.mDev_pos, byref(pErrorCode))
            MAXON_Motor.epos.VCS_DefinePosition(self.keyHandle, self.mDev_nodeID, 0, byref(pErrorCode))
            if pErrorCode.value != 0:
                raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            


            self.mDev_get_cur_pos()              # updating current position
            print_log (f"MAXON {self.devName}  HOMED on port = {self.mDev_port} /  position = {self.mDev_pos}" ) 


        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f"MAXON {self.devName}  HOME faled HOMING on port {self.mDev_port}, Unexpected Exception: {ex} ")
            return False         
        else:
            return True         


    def mutualControl(self):
        if self.dev_lock.locked():
            print_err(f'ERROR- The device {self.devName} (port:{self.mDev_port}, nodeID:{self.mDev_nodeID}) is active. Cant allow multiply activations')

            return False
        else:
            self.dev_lock.acquire()
            return True


    @staticmethod
    class smartLocker:                              # Mutex mechanism
        def __init__(self, lock):
            self.lock = lock
            if  self.lock:
                self.lock.acquire()
                # print_log(f'+++++++++ BLOCK IN ({self.lock} -- {"fh_lock" if self.lock is FH_Motor_v3.fh_lock else "NOT fh_lock"} +++++++++++')
        def __del__(self): 
            if  self.lock:
                # print_log(f'----------- BLOCK OUT ({self.lock}  -- {"fh_lock" if self.lock is FH_Motor_v3.fh_lock else "NOT fh_lock"})-----------')
                self.lock.release() 


#------------------------- U N I T E S T ----------------------------
# Stub class for MAXON motor for unit testing without hardware
class MAXON_Motor_Stub: 
    operation = namedtuple("operation", ["fw", "bw", "g2p", "stop"])
    devices:list[MAXON_Motor.portSp] = [
        MAXON_Motor.portSp('stub_dev', 'stub_protocol', 'stub_usb','stub_port', '9600', '12345', 1, 'stub_sensor'),
        MAXON_Motor.portSp('stub_dev2', 'stub_protocol', 'stub_usb','stub_port2', '9600', '67890', 2, 'stub_sensor2')
        ]
    


    def __init__(self, mxnDev:MAXON_Motor.portSp):
        self.mDev_pos:int = 0                                 #  current position 
        self.wd = None                                      # watch dog identificator
        self.mDev_SN = mxnDev.sn                                   # Serial N (0x1018:0x04)
        self.__stop_motion:threading.Event = threading.Event()  # Event to stop motion thread
        self.__operation:MAXON_Motor_Stub.operation = MAXON_Motor_Stub.operation.stop  # Operations enum
        self.rpm:int = 2000                                 # default speed in rpm 
        self.start_time: float = 0                                   # Start thread time
        self.devName:str = mxnDev.sn
        self.mDev_port:str = mxnDev.port 
        self.devNotificationQ = Queue()
        self.mDev_get_cur_pos()
        print_log(f'({self.devName}) Serial number = {self.mDev_SN} Position = {self.mDev_pos}')
        self.mDev_status = True

    def __del__(self):
        print_log(f'Releasing/deleting MAXON on port {self.mDev_port}')  
        self.__stop_motion.set()    

    @staticmethod
    def enum_devs(mxnDevice, mxnInterface)->list[MAXON_Motor.portSp]:
        return MAXON_Motor_Stub.devices

    @staticmethod
    def init_devices(mxnDevice=b'EPOS4', mxnInterface=b'USB')->list[MAXON_Motor.portSp]:
        print_log(f'Initializing MAXON Stub devices with Device={mxnDevice} Interface={mxnInterface}')
        return MAXON_Motor_Stub.devices
    
    def init_dev(self) -> bool:
        print_log(f'Initializing MAXON Stub device on port {self.mDev_port}, dev = {self.devName}')
        return True

    def mDev_get_actual_current(self) -> int:
        return 10
        

    def _is_pos_reached(self, target_pos:int, ex_limit:int) -> bool:
        print_log (f'Checking position reached on MAXON Stub port = {self.mDev_port}, dev = {self.devName}, target_pos = {target_pos}, ex_limit = {ex_limit}, current_pos = {self.mDev_pos}')
        if abs(self.mDev_pos - target_pos) <= 10:
            return True
        return False
        
    def  mDev_watch_dog_thread(self):
        self.__stop_motion.clear()
        self.devNotificationQ.queue.clear()
        print_log (f'>>> WatchDogStub MAXON  started on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}, operation = {self.__operation}')
        while (not self.__stop_motion.is_set()):
            if self.__operation == self.operation.fw:
                    self.mDev_pos += 10
            elif self.__operation == self.operation.bw:
                self.mDev_pos -= 10
            elif self.__operation == self.operation.g2p:
                if self.mDev_pos < self.new_pos:
                    self.mDev_pos += 10
                elif self.mDev_pos > self.new_pos:
                    self.mDev_pos -= 10
                else:
                    print_log (f'<<< WatchDogStub MAXON reached position on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}')
                    break
            time.sleep(0.1)

        self.devNotificationQ.put(True)
        self.__operation = self.operation.stop
        print_log (f'<<< WatchDogStub MAXON stopped on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}')
        return
    

    def  mDev_watch_dog(self):
        # self.start_time = time.time()
        self.wd = threading.Thread(target=self.mDev_watch_dog_thread)
        self.wd.start()
        return self.wd

    def mDev_stop(self)-> bool:
        self.__stop_motion.set()
        return True

    def go2pos(self, new_position, velocity = None, acceleration = None, deceleration = None, stall=None)->bool:
        print_log(f'MAXON Stub GO2POS {new_position} velocity = {velocity}, dev = {self.devName}, port = {self.mDev_port}')
        self.__operation = self.operation.g2p
        self.new_pos = new_position
        self.mDev_watch_dog()
        return True  

    def mDev_stall(self)->bool:
        return True

    def  mDev_forward(self, velocity = None, acceleration = None, deceleration = None, timeout=None, polarity:bool=None, stall = None)->bool:
        print_log(f'MAXON Stub FORWARD velocity = {velocity}, dev = {self.devName}, port = {self.mDev_port}, timeout={timeout}')
        self.__operation = self.operation.fw
        self.mDev_watch_dog()
        return True
    
    def  mDev_backward(self, velocity = None, acceleration = None, deceleration = None, timeout=None, polarity:bool = None, stall = None)-> bool:
        print_log(f'MAXON Stub BACKWARD velocity = {velocity}, dev = {self.devName}, port = {self.mDev_port}, timeout={timeout}')
        self.__operation = self.operation.bw                    # no need watchdog for zero speed
        self.mDev_watch_dog()
        return True
    
    def mDev_stored_pos(self): 
        return self.mDev_pos
   
    def mDev_get_cur_pos(self) -> int:
        return self.mDev_pos        

    def  mDev_reset_pos(self)->bool:
        self.mDev_stop()
        self.mDev_pos = 0
        return True


#Basic test of the module
    
if __name__ == "__main__":

    import PySimpleGUI as sg

    image_left = './Images/button_left_c.png'
    image_right = './Images/button_right_c.png'

# OFF button diagram
    toggle_btn_off = b'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'

# ON button diagram
    toggle_btn_on = b'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'

    gif103 = b'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'


    BORDER_COLOR = '#C7D5E0'
    DARK_HEADER_COLOR = '#1B2838'
    BPAD_TOP = ((20,20), (20, 10))
    BPAD_LEFT = ((20,10), (0, 0))
    BPAD_LEFT_INSIDE = (0, (10, 0))
    BPAD_RIGHT = ((10,20), (10, 0))

    top_banner = [
                    [sg.Text('UNITEST', font='Any 12', background_color=DARK_HEADER_COLOR, enable_events=True, \
                                grab=False), sg.Push(background_color=DARK_HEADER_COLOR),
                    sg.Text(f'v 1.0  © 2026', font='Any 12', background_color=DARK_HEADER_COLOR)],
                    ]
    
    CUSTOM_MENU_RIGHT_CLICK_VER_LOC_EXIT = ['', ['Version', 'File Location', 'Exit']]



    def setGUI(_num_of_devs: int)->list:
        dev_layout = list()
        distance_rotators = _num_of_devs
        rotator_in_GUI = 4
        for _it in range (0, distance_rotators // rotator_in_GUI ):
            dev_layout.append(sg.Column(dist_rotators_frames(_it + 1, _it + rotator_in_GUI ), scrollable=False, vertical_scroll_only=True, \
                                key='COLUMN-Z1', vertical_alignment='center', justification='center',pad=0, expand_y = 'True'))
        last_rotator_column_list = list()
        if (distance_rotators % rotator_in_GUI) > 0:
            print_log(f'Adding rotators: {(distance_rotators // rotator_in_GUI) * rotator_in_GUI  + 1} - {distance_rotators}')
            last_rotator_column_list = dist_rotators_frames((distance_rotators // rotator_in_GUI) * rotator_in_GUI  + 1, \
                    distance_rotators)
        
        dev_layout.append(sg.Column(last_rotator_column_list, \
                scrollable=False, vertical_scroll_only=True, \
                key='COLUMN-Z1', vertical_alignment='center', justification='center',pad=0, expand_y = 'True'))

        layout = [
                    [sg.Frame('', top_banner,   pad=(0,0), background_color=DARK_HEADER_COLOR,  expand_x=True, \
                                border_width=0, grab=True)],
                    dev_layout,
                    
                    [sg.Sizegrip(background_color=BORDER_COLOR)]
                    ]
        return layout

    def LEDIndicator(key=None, radius=30):
        return sg.Graph(canvas_size=(radius, radius),
                graph_bottom_left=(-radius, -radius),
                graph_top_right=(radius, radius),
                pad=(0, 0), key=key)

    def SetLED(window, key, color):
        graph = window[key]
        graph.erase()
        graph.draw_circle((0, 0), 12, fill_color=color, line_color=color)
    
    def dist_rotators_block(i):
        return ([
            [sg.Push(), sg.Text(f'R{i}', font='Any 10'), \
            sg.Text(f'', font='Any 10', key = f'-{i}-DIST_ROTATOR-TITLE-'), LEDIndicator(f'_dist_rotator_{i}_'), sg.Push()],
            [sg.T('Position'), sg.Text("_", size=(8, 1), relief = sg.RELIEF_SUNKEN, justification = 'center', \
                border_width = 2, key=f'-{i}-DIST_ROTATOR_POSSITION-'), sg.Button(button_text = "Reset", key=f'-{i}-DIST_ROTATOR_TARGET_RESET-') ],
            [sg.Text('Target'), sg.Input(size=(10, 1), enable_events=True, key=f'-{i}-DIST_ROTATOR_TARGET-', \
                font=('Arial Bold', 8), justification='left'), sg.Button(button_text = "Set & Go", key=f'-{i}-DIST_ROTATOR_POS_SET-')],
            [sg.Button( button_color=sg.TRANSPARENT_BUTTON, image_filename = image_left, image_size=(22, 24), \
                image_subsample=2, border_width=0, key=f'-{i}-DIST_ROTATOR_LEFT-'),
                sg.Frame('',[[sg.Text('Velocity (RPM)')], [sg.Input(size=(15, 1), enable_events=True, key=f'-{i}-DIST_ROTATOR_VELOCITY-', \
                    font=('Arial Bold', 8), justification='left')]], border_width=0),
            sg.Button( button_color=sg.TRANSPARENT_BUTTON, image_filename = image_right, image_size=(22, 24), \
                image_subsample=2, border_width=0, key=f'-{i}-DIST_ROTATOR_RIGHT-')], 
            [sg.Text("_", size=(6, 1), relief = sg.RELIEF_SUNKEN, justification = 'center', \
                border_width = 2, key=f'-{i}-DIST_ROTATOR_CUR_DISPLAY-'),
                sg.Text(f'Stop (mA) >\n< Curr. (mA)'), sg.Input(size=(8, 1), enable_events=True, key=f'-{i}-DIST_ROTATOR-CURR-')],
            [sg.Button(button_text = 'Stop/Release',  key=f'-{i}-DIST_ROTATOR_STOP-')]]

    )

    def dist_rotators_frames(line_s, line_e):
        return (
            [[sg.Frame('', dist_rotators_block(i), border_width=3, \
                                    expand_x=True, expand_y=True, element_justification = "center")]  for i in range (line_s, line_e+1) ]
    )


    def StartGUI (layout, title_str )->sg.Window:
        window = sg.Window(title_str, layout, margins=(0,0), background_color=BORDER_COLOR,  \
                        # no_titlebar=False, resizable=False, right_click_menu=sg.MENU_RIGHT_CLICK_EDITME_VER_LOC_EXIT, \
                        no_titlebar=False, resizable=True, right_click_menu=CUSTOM_MENU_RIGHT_CLICK_VER_LOC_EXIT, \
                        element_justification='c', finalize = True)
                        # element_padding=(0,0), element_justification='c', finalize = True)
        

        window.read(timeout=0) 
        window.Finalize()
        # print_log(f'Starting GUI. trolley = {trolley_motors}, zaber ={zaber_motors}, gripper = {gripper_motors}')

        # deactivateGUI(window)

        sg.PopupAnimated(image_source=gif103, text_color='blue', 
                        message='Loading...',background_color='grey', time_between_frames=100)    

        return window

    def formFillProc(event, values, window, realNum = False, positiveNum = True, defaultValue = 0, max_size = 0):
        from common_utils import real_num_validator, int_num_validator, real_validator, int_validator

        if realNum:
            valValidator = real_validator
            numValidator = real_num_validator
            cast = float
        else:
            valValidator = int_validator
            numValidator = int_num_validator
            cast = int

        if max_size > 0 and len(str(values[event])) > max_size:
            print_DEBUG(f'Oversize - {values[event]}= {len(str(values[event]))}')
            window[event].update(values[event][:-1])
            return values[event][:-1]


        if not valValidator(values[event], positive = positiveNum):    
            window[event].update(values[event][:-1])

            if not numValidator(values[event][:-1], positive = positiveNum):    #invalid edited value
                if defaultValue:
                    window[event].update(str(defaultValue))   
                    print_DEBUG(f'DEBUG: if not numValidator and there is default value -> window[{event}].update({str(defaultValue)})')
            
                else:                       # there is no defail value
                    window[event].update('')   

            else:      
                pass                     # valid edited value


        else:
            window[event].update(values[event])

        ret_value = values[event]
        ret_value = cast(ret_value) if numValidator(ret_value) else cast(defaultValue)

        return ret_value

    def main_loop():
        from common_utils import real_num_validator, int_num_validator, real_validator, int_validator


    # Layout (COM / on / off)
        # layout = [
        #     [sg.Frame('', la_gripper,  expand_x=True,  relief=sg.RELIEF_GROOVE, \
        #             border_width=3, vertical_alignment='center', element_justification = "center")],
        #     [sg.Frame('', trolley,  expand_x=True,  relief=sg.RELIEF_GROOVE, \
        #             border_width=3, vertical_alignment='center', element_justification = "center")]

        # ]

        # window = sg.Window('Unitest', layout, finalize = True)

        layout = setGUI(1)
        window = StartGUI(layout, 'UNITEST')   

        _mxdev:MAXON_Motor
        devs:MAXON_Motor.portSp = MAXON_Motor.init_devices() # default parameters
                                            # init devices and pereferials 



        down = graphic_off = True

        sg.PopupAnimated(image_source=None)

        if devs is None or len(devs) == 0:
            print_err(f"No devices found (dev = {devs})")       
            sg.Popup('No devices found', title='Error')
            sys.exit()

        dev_rotator = MAXON_Motor(devs[0]) 
        
        


    #-----------------------------------------------------------   
        # if dev_trolley:
        #     window['-TROLLEY_POSSITION-'].update(value = dev_trolley.mDev_pos)
        #     window['-TROLLEY_VELOCITY-'].update(value = dev_trolley.rpm)

        while True:

            #get event
            event, values = window.read(timeout=100)

            if not 'TIMEOUT' in event:
                print(event, values)

            #When the window is closed or the Exit button is pressed
            if event in (sg.WIN_CLOSED, 'Exit'):
                print_log(f'Exiting')
                # sys.exit()
                break


            
            elif  f'-DIST_ROTATOR_TARGET-' in event:
                new_val = formFillProc(event, values, window, realNum = False, positiveNum = False, defaultValue = str(dev_rotator.mDev_get_cur_pos()))
                dev_rotator.mDev_pos = new_val

                    #
            elif '-DIST_ROTATOR_VELOCITY-' in event:
                new_val =  formFillProc(event, values, window, realNum = False, positiveNum = False, defaultValue = str(dev_rotator.DevOpSPEED))
                dev_rotator.rpm = new_val

            elif '-DIST_ROTATOR_POS_SET-' in event:
                i = event[1]

                t_target = values[f'-{i}-DIST_ROTATOR_TARGET-']
                if not int_num_validator(t_target):
                    print_err (f'Wrong target value:->{t_target}<-')
                    continue

                go_pos = int(t_target)

                print_log(f'Move DIST ROTATOR  to {go_pos} position')

                dev_rotator.go2pos(go_pos)

                # DeActivateMotorControl(window, f'--DIST_ROTATOR--', dev_rotator.c_gui)
            
            elif '-DIST_ROTATOR_RIGHT-' in event:
                
                # DeActivateMotorControl(window, '--DIST_ROTATOR--', dev_rotator.c_gui)
                # wTask = pm.WorkingTask(pm.CmdObj(device=dev_rotator, cmd=pm.OpType.go_fwrd_on), sType = pm.RunType.single)
                dev_rotator.mDev_forward()


            elif '-DIST_ROTATOR_LEFT-' in event:
                # DeActivateMotorControl(window, '--DIST_ROTATOR--', dev_rotator.c_gui)

                # wTask = pm.WorkingTask(pm.CmdObj(device=dev_rotator, cmd=pm.OpType.go_bcwrd_off), sType = pm.RunType.single)
                dev_rotator.mDev_backwrd()

            
            elif '-DIST_ROTATOR_STOP-' in event:
                # wTask = pm.WorkingTask(pm.CmdObj(device=dev_rotator, cmd=pm.OpType.stop), sType = pm.RunType.single)
                dev_rotator.mDev_stop()

                # ActivateMotorControl(window, '--DIST_ROTATOR--', dev_rotator.c_gui)
                
            elif '-DIST_ROTATOR_TARGET_RESET-' in event:
                i = event[1]

                # wTask = pm.WorkingTask(pm.CmdObj(device=dev_rotator,cmd=pm.OpType.home), sType = pm.RunType.single)
                dev_rotator.mDev_reset_pos()

                window[f'-{i}-DIST_ROTATOR_POSSITION-'].update(value = 0)
                window[f'-{i}-DIST_ROTATOR_TARGET-'].update(value = 0) 
            
            elif '-DIST_ROTATOR-CURR-' in event:
                new_val = formFillProc(event, values, window, realNum = False, positiveNum = True, defaultValue = str(dev_rotator.DEFAULT_CURRENT_LIMIT))
                dev_rotator.el_current_limit = new_val

     
        window.close()
        

#=========================== block  __name__ == "__main__" ================
if __name__ == "__main__":
    import datetime, logging
    logFileDate = datetime.datetime.now().strftime(f"LOG_%Y_%m_%d_%H_%M.txt")
    format = "%(asctime)s: %(filename)s--%(funcName)s/%(lineno)d -- %(thread)d [%(threadName)s] %(message)s" 
    logging.basicConfig(format=format, handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logFileDate, mode="w")], encoding='utf-8', level=logging.DEBUG, datefmt="%H:%M:%S")
#---------------  end of block  __name__ == "__main__" -------------------


if __name__ == "__main__":
    main_loop()