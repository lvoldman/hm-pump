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


from common_utils import print_log, print_inf, print_err, print_DEBUG, exptTrace, s16, s32, num2binstr, set_parm, get_parm, void_f, assign_parm

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
    devices:MAXON_Motor.portSp = None               # list of devices
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
        self.mDev_type = None                                 # devise type (DevType.ROTATOR / DevType.GRIPPERv3 / DevType.DIST_ROTATOR / DevType.TIME_ROTATOR (SPINNER))
        self.mDev_pos:int = 0                                 #  current position 
        self.el_current_limit:int = 0                       # electrical current limit to stop 
        self.el_current_on_the_fly:int = 0                  # On-the-fly current                    
        self.wd = None                                      # watch dog identificator
        self.__qStopDec:int = None                            # Quick stop decaliration 
        self.mDev_SN = mxnDev.sn                                   # Serial N (0x1018:0x04)
        self.mDev_status = False                              # device status (bool) / used for succesful initiation validation
        self.mDev_in_motion = False                           # is device in motion
        self.possition_control_mode = False                 # TRUE - control possition, FALSE - don't
        self.time_control_mode = False                      # TRUE - time control
        self.mDev_pressed = False                             # is motion button pressed
        self.gripper_onof = True                            # True means off )))
        self.new_pos = 0
        self.sensorType = mxnDev.sensortype
#------- Bad practice --------
        self.el_voltage:int = self.DEAFULT_VELOCITY_EV_VOLTAGE       # forCOMPATABILTY ONLY (BUGBUG)
        self.rpm:int = self.DevOpSPEED 
#------- Bad practice --------
#############  Communication ##########
        self.__keyHandle = None
        self.__nodeID = None
#######################################        
        self.start_time: float = 0                                   # Start thread time
        self.success_flag = True                            # end of op flag
        self.rotationTime:float = 0                               # rotation time
        self.diameter = MAXON_Motor.DIAMETER
        self.gear = MAXON_Motor.GEAR
        self.devName:str = mxnDev.sn
        self.__title = None
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


            print_inf(f'({devName}) Serial number = {self.mDev_SN} Possition = {self.mDev_pos}')
            # self._set_QuickStopPolarity(False)

        except Exception as ex:

            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
   
            print_err(f"({devName}) ERROR. Initiating MAXON port {self.mDev_port} was lost. Unexpected Exception: {ex}")
            return                                  # no valid FAULHABBER motor can be added
        
        else:
            self.mDev_status = True
            pass

        if self.mDev_port in MAXON_Motor.activated_devs:
            print_err(f"**ERROR** . ({devName}) Device with port = {self.mDev_port} already activated")
        else:
            MAXON_Motor.activated_devs.append(self.mDev_port)
        



    

    def __del__(self):
        pErrorCode=c_uint()

        print_inf(f'Releasing/deleting MAXON on port {self.mDev_port}')  

        self.mDev_in_motion = False

        try:

            MAXON_Motor.epos.VCS_SetDisableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode)) # disable device
            MAXON_Motor.epos.VCS_CloseDevice(self.keyHandle, byref(pErrorCode))


            print_inf(f'({self.devName}) MAXON disabled on port {self.mDev_port}.')
            MAXON_Motor.activated_devs.remove(self.mDev_port)
        except  Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'({self.devName})  MAXON device on port {self.mDev_port} could not be closed. Exception: {ex} of type: {type(ex)}.')
        finally:
            pass


        if not len(MAXON_Motor.activated_devs):         # if no more active devices - deactivate
            print_inf(f'No more active MAXON devices. Exiting.')
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
            print_inf(f'Looking for maxon devices, mxnDevice = {mxnDevice}, mxnInterface = {mxnInterface}')
            MAXON_Motor.enum_devs(mxnDevice, mxnInterface)

            if len(MAXON_Motor.devices) == 0:
                print_inf("No MAXON devices detected in the system")
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


    def _set_QuickStopPolarity(self, high = True):
        print_inf(f'Setting active polarity on Digital Input 4 for {self.mDev_type} type on port {self.mDev_port} to {"HIGHT" if high else "LOW"}')
        try:
            _mask_polarity = MAXON_Motor.MXN_cmd(self.mDev_port, READ_HIGH_POLARITY, keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock = MAXON_Motor.mxn_lock)
            if len(_mask_polarity) > 0:
                _mask:int = _mask_polarity[0].answData
            else: 
                print_err(f'Error reading polarity on Digital Input 4 for {self.mDev_type} type on port {self.mDev_port}')
                return False        

            _bit_mask = (0b0000000000000001 << (DIG_INP_4_CONF-1))
            if high:
                if (_mask >> _bit_mask) & 0b0000000000000001 == 0:
                    print_log(f'Setting quickstop on chan {DIG_INP_4_CONF} polarity to HIGH')
                    _mask = _mask | _bit_mask
                else:
                    print_log(f'Quickstop polarity on chan {DIG_INP_4_CONF} already HIGH')

            else: 
                if (_mask >> _bit_mask) & 0b0000000000000001 == 0:
                    print_log(f'Setting quickstop polarity on chan {DIG_INP_4_CONF} to LOW')
                    _mask = _mask & ~_bit_mask
                else:
                    print_log(f'Quickstop polarity on chan {DIG_INP_4_CONF} already LOW')                    
            
            MAXON_Motor.MXN_cmd(self.mDev_port, [(INP_POLARITY_CTL, 0x2, _mask, 0x2)], keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock = MAXON_Motor.mxn_lock)

            
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON Quick Stop setting on port {self.mDev_port} failed. Exception: {ex} of type: {type(ex)}.')
            return False

        return True

    def _activateQuickStop(self) -> bool:
        pErrorCode = c_uint()
        print_inf(f'Activation Quick Stop on Digital Input 4 for {self.mDev_type} type on port {self.mDev_port}')
        # try:

        #     MAXON_Motor.epos.VCS_DigitalInputConfiguration(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), \
        #                                   4,    # DigitalInputNb
        #                                   5,    # Quick stop / DIC_QUICK_STOP
        #                                   1,    # Mask  1: Functionality state will be displayed / 0: not displayed (not supported with EPOS4) 
        #                                   0,    # Polarity, 1: Low active / 0: High active
        #                                   0 ,   # ExecutionMask, 1: Set the error routine / Only for positive and negative
        #                                   pErrorCode)
        #     if pErrorCode.value != 0:
        #             print_log(f'ERROR setting Digital Input. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        #             # raise Exception(f'ERROR setting Digital Input. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

        try:
            MAXON_Motor.MXN_cmd(self.mDev_port, ACTIVATE_QUICK_STOP, keyHandle=self.__keyHandle, nodeID=self.__nodeID,lock = MAXON_Motor.mxn_lock)


        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON Quick Stop setting on port {self.mDev_port} failed. Exception: {ex} of type: {type(ex)}.')
            return False

        return True

    def _deActivateQuickStop(self) -> bool:
        pErrorCode = c_uint()
        print_inf(f'Deactivation Quick Stop on Digital Input 4 for {self.mDev_type} type on port {self.mDev_port}')
        # try:

        #     MAXON_Motor.epos.VCS_DigitalInputConfiguration(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), \
        #                                   4,    # DigitalInputNb
        #                                   12,   # General purpose D / DIC_GENERAL_PURPOSE_D
        #                                   1,    # Mask  1: Functionality state will be displayed / 0: not displayed (not supported with EPOS4) 
        #                                   0,    # Polarity, 1: Low active / 0: High active
        #                                   0 ,   # ExecutionMask, 1: Set the error routine / Only for positive and negative
        #                                   pErrorCode)
            
        #     if pErrorCode.value != 0:
        #             print_log(f'ERROR setting Digital Input. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        #             # raise Exception(f'ERROR setting Digital Input. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

        try:
            MAXON_Motor.MXN_cmd(self.mDev_port, DEACTIVATE_QUICK_STOP, keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock = MAXON_Motor.mxn_lock)

        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON deactivating Quick Stop setting on port {self.mDev_port} failed. Exception: {ex} of type: {type(ex)}.')
            return False

        return True


    def init_dev(self, type) -> bool:
        
        self.mDev_type = type
        pErrorCode = c_uint()
        print_inf(f'Clearing  MAXON devise of {self.mDev_type} type on port {self.mDev_port}')
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

    def  mDev_watch_dog_thread(self):
        
        print_inf (f'>>> WatchDog MAXON  started on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}')
        time.sleep(self.MEASUREMENT_DELAY)                 # waif for a half of sec
        self.success_flag = True
        self.mDev_in_motion = True
        max_GRC:int = 0
        while (self.mDev_in_motion):
            try:
                pCurrentIs = c_int32(0)
                pErrorCode = c_uint()
                pTargetReached = c_bool(False)
                pQuickStop = c_bool(False)
                pState = c_uint()
                pVelocityIs = c_long()

#------------------------
                MAXON_Motor.epos.VCS_GetCurrentIs(self.keyHandle, self.mDev_nodeID, byref(pCurrentIs), byref(pErrorCode))
                actualCurrentValue:int = s16(pCurrentIs.value)
#------------------------
                # answA = MAXON_Motor.MXN_cmd(self.mDev_port, [MAXON_CURRENT_ACTUAL_VALUE_QUERY], keyHandle=self.__keyHandle, nodeID=self.__nodeID, lock=MAXON_Motor.mxn_lock)
                # if len(answA) == 0:
                #     print_err(f'WatchDog MAXON failed read MAXON_CURRENT_ACTUAL_VALUE_QUERY on port  {self.mDev_port}.')
                #     continue

                # actualCurrentValue:int = s32(answA[0].answData)

#------------------------

                self.el_current_on_the_fly = actualCurrentValue

                print_DEBUG(f'WatchDog MAXHON Actual Current Value = {actualCurrentValue}')
                if pErrorCode.value == 0:
                   
                    max_GRC = abs(actualCurrentValue) if abs(actualCurrentValue) > max_GRC else max_GRC

                    if (int(abs(actualCurrentValue)) > int(self.el_current_limit)):
                        print_inf(f' WatchDog MAXON: Actual Current Value = {actualCurrentValue}, Limit = {self.el_current_limit}')
                        if (self.mDev_type == DevType.TROLLEY or self.mDev_type == DevType.DIST_ROTATOR) and self.possition_control_mode:
                            _pos = self.mDev_get_cur_pos()
                            if abs(_pos - self.new_pos) > self.EX_LIMIT:
                                print_log(f'Desired position [{self.new_pos}] is not reached. Current position = {_pos}')
                                self.success_flag = False
                        break


                else:
                    print_err(f'WatchDog MAXON failed get Actual Current Value on port  {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)} ')


                
                if self.mDev_type == DevType.GRIPPERv3:
                    end_time = time.time()
                    if end_time - self.start_time > self.GRIPPER_TIMEOUT:
                        print_inf(f' WatchDog MAXON: GRIPPER operation canceled by timeout, port = {self.mDev_port}, actual current value = {actualCurrentValue}, Limit = {self.el_current_limit}, max GRC = {max_GRC} ')
                        break

                if self.time_control_mode:
                    end_time = time.time()
                    if end_time - self.start_time > self.rotationTime:
                        print_inf(f' WatchDog MAXON: TIME/DIST ROTATOR operation completed, port = {self.mDev_port}, actual current value = {actualCurrentValue}, Limit = {self.el_current_limit}, max GRC = {max_GRC} ')
                        break

                if (self.mDev_type == DevType.TROLLEY or self.mDev_type == DevType.DIST_ROTATOR) :


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

                        # if pQuickStop.value or _qStop or _qStop_state or ( (time.time() - self.start_time > self.CURRENT_WAIT_TIME)  \
                                                                        # and  ((abs(actualCurrentValue) <= self.IDLE_DEV_CURRENT))):        # Quick stop is active 
                        
                        # if pQuickStop.value or _qStop or _qStop_state :        # Quick stop is active 
                        
                            print_inf(f'MAXON entered QuickStop state at port {self.mDev_port}. Exiting watchdog')
                            print_log(f'{self.devName}: _qStop = {_qStop}(status =  0x{_status:02x} <> {num2binstr(_status)}) // state = {pState.value} (QuckStop by state = {_qStop_state}) //  pQuickStop.value = { pQuickStop.value} //  current = {actualCurrentValue}mA // velocity = {pVelocityIs.value}')

                            # self._deActivateQuickStop()
                            break
                    else:
                        print_err(f'WatchDog MAXON failed read QuickStop status on port = {self.mDev_port}. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                    if self.possition_control_mode:

                        MAXON_Motor.epos.VCS_GetMovementState(self.keyHandle, self.mDev_nodeID, byref(pTargetReached), byref(pErrorCode))

                        print_DEBUG(f'WatchDog MAXON: POSITION REACHED (bit 10 at statusword  )={pTargetReached.value}')
                        if pErrorCode.value == 0:


                            if pTargetReached.value:        # Position reached - bit 10 at statusword 
                                print_inf(f'POSITION REACHED on  MAXON port {self.mDev_port}. Exiting watchdog')

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
        print_inf(f' WatchDog MAXON: Start time = {self.start_time}, end time ={end_time}, delta = {end_time - self.start_time}')
        print_inf (f'>>> WatchDog MAXON  completed on  port = {self.mDev_port}, dev = {self.devName}, position = {self.mDev_pos}, minimal operation time = {self.MINIMAL_OP_DURATION}')
        if end_time - self.start_time - self.MEASUREMENT_DELAY < self.MINIMAL_OP_DURATION:
            print_inf(f' WatchDog MAXON: Abnormal termination on port = {self.mDev_port}')
            self.success_flag = False

        time.sleep(0.1)

    
        if self.mDev_in_motion:
            print_inf(f'Thread is being stoped')
            self.mDev_stop()
            
        
        if self.dev_lock.locked():
            self.dev_lock.release()
        else:
            print_err(f'-WARNING unlocket mutual access mutex')


        self._deActivateQuickStop()
        self.mDev_get_cur_pos()
        self.devNotificationQ.put(self.success_flag)
        
        return
    

    def  mDev_watch_dog(self):
        self.start_time = time.time()
        self.wd = threading.Thread(target=self.mDev_watch_dog_thread)
        self.wd.start()
        return self.wd

    def mDev_stop(self)-> bool:

        # if self.dev_lock.locked():
        #     self.dev_lock.release()

        try:
            pErrorCode = c_uint()
            MAXON_Motor.epos.VCS_SetQuickStopState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
            
            if self.STALL_RELEASE:
                MAXON_Motor.epos.VCS_SetDisableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                

            self.mDev_in_motion = False
            print_inf(f'Motor of {self.mDev_type} type is being disabled on port: {self.mDev_port}')
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
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
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

    def gripper_on(self)-> bool:
        if not self.mutualControl():
            return False
        
        pErrorCode = c_uint()
        self.success_flag = True
        

        
        try:

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                    print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
        
            if self.sensorType == 0:                        # use current mode
                print_inf(f'gripper_on on port: {self.mDev_port}, velocity/voltage = {self.el_voltage}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}')
                MAXON_Motor.epos.VCS_ActivateCurrentMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Current Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                MAXON_Motor.epos.VCS_SetCurrentMustEx(self.keyHandle, self.mDev_nodeID, self.el_voltage, byref(pErrorCode))
                if pErrorCode.value != 0:
                        raise Exception(f'ERROR: Setting Current: VCS_SetCurrentMustEx(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            else:                                           # sensor is present
                print_inf(f'gripper_on on port: {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')


                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
                if pErrorCode.value != 0:
                        print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, self.rpm, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')


                                                                                                          
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON gripper failed on port = {self.mDev_port}. Exception: [{ex}].')
            self.success_flag = False
            self.mDev_stop()
            if self.dev_lock.locked():
                self.dev_lock.release()
            return False
            
        self.gripper_onof = True    
        self.mDev_watch_dog()
        return True

    def gripper_off(self)->bool:
        if not self.mutualControl():
            return False
        
        self.success_flag = True
        pErrorCode = c_uint()
        

        try:
            

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                    print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
            if self.sensorType == 0:                        # use current mode
                print_inf(f'gripper_off on port: {self.mDev_port}, velocity/voltage = -{self.el_voltage}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}')
                MAXON_Motor.epos.VCS_ActivateCurrentMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Current Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                MAXON_Motor.epos.VCS_SetCurrentMustEx(self.keyHandle, self.mDev_nodeID, (-1)*self.el_voltage, byref(pErrorCode))
                if pErrorCode.value != 0:
                        raise Exception(f'ERROR: Setting Current: VCS_SetCurrentMustEx(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

            else:  

                print_inf(f'gripper_off on port: {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')

                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
                if pErrorCode.value != 0:
                        print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, (-1)*self.rpm, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')


                                                                                                          
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON gripper failed on port = {self.mDev_port}. Exception: [{ex}].')
            self.success_flag = False
            self.mDev_stop()
            if self.dev_lock.locked():
                self.dev_lock.release()
            return False
            
        self.gripper_onof = False    
        self.mDev_watch_dog()

        return True
    

    def timeRotaterFw(self, time, velocity = None) -> bool:
        pErrorCode = c_uint()
        
        if not self.mutualControl():
            return False
        
        if velocity == None:
            velocity = int(self.rpm)


        self.success_flag = True
        self.possition_control_mode = False
        self.time_control_mode = True 
        self.rotationTime = time
        print_inf(f'Going forward (time) on port = {self.mDev_port} for {time} seconds, velocity = {velocity}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')

        try:
            

            if self.sensorType == 0 and not (velocity == 0):                        # use current mode
                self.currentModeMove(self.el_voltage)
            
            else:

                MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
                if pErrorCode.value != 0:
                        print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                if (velocity != 0):
                    MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, velocity, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                else:           # speed == 0
                    MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           

                                                                                                          
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON Time Rotator failed on port = {self.mDev_port}. Exception: [{ex}].')
            self.success_flag = False
            self.mDev_stop()
            if self.dev_lock.locked():
                self.dev_lock.release()
            return False
        
        
        else:
            print_inf (f"MAXON time FW started on port = {self.mDev_port} " )
        
        self.mDev_watch_dog()
        return True
        

    def timeRotaterBw(self, time, velocity = None)->bool:
        pErrorCode = c_uint()

        if not self.mutualControl():
            return False
        
        if velocity == None:
            velocity = int(self.rpm)

        self.success_flag = True
        self.possition_control_mode = False
        self.time_control_mode = True 
        self.rotationTime = time
        print_inf(f'Going backward (time) on port = {self.mDev_port}  for {time} seconds, velocity = {velocity}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')

      
        try:
            if self.sensorType == 0 and not (velocity == 0):                        # use current mode
                self.currentModeMove((-1)*self.el_voltage)
            
            else:

                MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
                if pErrorCode.value != 0:
                    print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                if (velocity != 0):
                    MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        print_err(f'WARNING: Setting Velocity Profile: VCS_SetVelocityProfile(Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID})  pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                    MAXON_Motor.epos.VCS_MoveWithVelocity(self.keyHandle, self.mDev_nodeID, (-1)*velocity, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR Operating moving with Velocity. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')

                else:           # speed == 0
                    MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                    if pErrorCode.value != 0:
                        raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           
                                                                                                          
        except Exception as ex:
            e_type, e_filename, e_line_number, e_message = exptTrace(ex)
            print_err(f'MAXON Time Rotator failed on port = {self.mDev_port}. Exception: [{ex}].')
            self.success_flag = False
            self.mDev_stop()
            if self.dev_lock.locked():
                self.dev_lock.release()
            return False
        
        else:
            print_inf (f"MAXON time BW started on port = {self.mDev_port} " )
 

        self.mDev_watch_dog()
        return True



    def go2pos(self, new_position, velocity = None, stall=None)->bool:
        if not self.mutualControl():
            return False
        
        self.new_pos = new_position
        if velocity == None:
            velocity = int(self.rpm)

        self.success_flag = True
        self.possition_control_mode = True
        self.time_control_mode = False 
        print_inf(f'MAXON GO2POS {new_position} velocity = {velocity}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration} ')
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
                                                        MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode)) 
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

        self.mDev_in_motion = False

        if self.dev_lock.locked():
            self.dev_lock.release()
        
        return True



    def  mDev_forward(self, velocity = None, timeout=None, polarity:bool=None, stall = None)->bool:
        if not self.mutualControl():
            return False
        
        if not velocity == None:
            self.rpm = int(velocity)

        self._activateQuickStop()

        if polarity is not None:
            self._set_QuickStopPolarity(polarity)

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
                print_inf(f'Going stall on port = {self.mDev_port}')
                MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           
            elif (self.rpm != 0):
                print_inf(f'Going forward on port = {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')

                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
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
            print_inf (f"MAXON forward/stall started on port = {self.mDev_port}" )
        
        if  self.rpm:                       # no need watchdog for zero speed
            self.mDev_watch_dog()
        else: 
            return self.mDev_stop()

        return True
    

    def  mDev_backwrd(self, velocity = None, timeout=None, polarity:bool = None, stall = None)-> bool:
        if not self.mutualControl():
            return False
        
        if not velocity == None:
            self.rpm = int(velocity)

        self._activateQuickStop()

        if polarity is not None:
            self._set_QuickStopPolarity(polarity)

        self.success_flag = True
        self.possition_control_mode = False

        if timeout:
            self.time_control_mode = True
            self.rotationTime =  float(timeout)
        else:
            self.time_control_mode = False

        print_inf(f'Going backward on port = {self.mDev_port}, velocity = {self.rpm}')

      
        try:
            pErrorCode = c_uint()

            MAXON_Motor.epos.VCS_ClearFault(c_void_p(self.keyHandle) , c_uint16(self.mDev_nodeID), byref(pErrorCode))
            if pErrorCode.value != 0:
                print_err(f'ERROR clearing Faults. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
            
            if self.rpm == 0:
                print_inf(f'Going stall on port = {self.mDev_port}')
                MAXON_Motor.epos.VCS_HaltVelocityMovement(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR halting device (speed = 0). pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
           
            elif (self.rpm != 0):
                print_inf(f'Going backward on port = {self.mDev_port}, velocity = {self.rpm}, Handle = {self.keyHandle}, nodeID = {self.mDev_nodeID}, acc = {MAXON_Motor.acceleration}, dec = {MAXON_Motor.deceleration}')

                MAXON_Motor.epos.VCS_ActivateProfileVelocityMode(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR Activation Profile Velocity Mode. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetEnableState(self.keyHandle, self.mDev_nodeID, byref(pErrorCode))
                if pErrorCode.value != 0:
                    raise Exception(f'ERROR enabling Device. pErrorCode =  0x{pErrorCode.value:08x} / {ErrTxt(pErrorCode.value)}')
                MAXON_Motor.epos.VCS_SetVelocityProfile(self.keyHandle, self.mDev_nodeID, MAXON_Motor.acceleration, MAXON_Motor.deceleration, byref(pErrorCode))
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
            print_inf (f"MAXON backward/stall started on port = {self.mDev_port}" )
 

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
        print_inf (f"MAXON {self.devName} starting HOMING on port = {self.mDev_port} /  position = {self.mDev_pos}" ) 

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
            print_inf (f"MAXON {self.devName}  HOMED on port = {self.mDev_port} /  position = {self.mDev_pos}" ) 


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
    
if __name__ == "__main__":

    import PySimpleGUI as sg

    image_left = './Images/button_left_c.png'
    image_right = './Images/button_right_c.png'

# OFF button diagram
    toggle_btn_off = b'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'

# ON button diagram
    toggle_btn_on = b'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'


    trolley  = [[sg.Push(), sg.Text('Trolley', font='Any 20'),  sg.Push()],
            [sg.T('Position'), sg.Text("_", size=(10, 1), relief = sg.RELIEF_SUNKEN, justification = 'center', \
                border_width = 2, key='-TROLLEY_POSSITION-'), sg.Button(button_text = "Reset", key='-TROLLEY_TARGET_RESET-') ],
            [sg.Text('Target'), sg.Input(size=(10, 1), enable_events=True, key='-TROLLEY_TARGET-', \
                font=('Arial Bold', 10), justification='left'), sg.Button(button_text = "Set & Go", key='-TROLLEY_POS_SET-')],
            [sg.Button( button_color=sg.TRANSPARENT_BUTTON, image_filename = image_left, image_size=(55, 60), \
                image_subsample=2, border_width=0, key='-TROLLEY_LEFT-'),
                sg.Frame('',[[sg.Text('Velocity (RPM)')], [sg.Input(size=(15, 1), enable_events=True, key='-TROLLEY_VELOCITY-', \
                    font=('Arial Bold', 10), justification='left')]], border_width=0),
            sg.Button( button_color=sg.TRANSPARENT_BUTTON, image_filename = image_right, image_size=(55, 60), \
                image_subsample=2, border_width=0, key='-TROLLEY_RIGHT-')], 
            [sg.Button(button_text = 'Stop',  key='-TROLLEY_STOP-')]]
    
    la_gripper = [[sg.Button('', image_data=toggle_btn_off, key='ONOFF', \
                button_color=(sg.theme_background_color(), sg.theme_background_color()), border_width=0)], 
                [sg.Button('Exit')]]

    def setGUI(_num_of_devs: int)->list:
        dev_layout = list()
        distance_rotators = _num_of_devs
        rotator_in_GUI = 4
        for _it in range (0, distance_rotators // rotator_in_GUI ):
            dev_layout.append(sg.Column(dist_rotators_frames(_it + 1, _it + rotator_in_GUI ), scrollable=False, vertical_scroll_only=True, \
                                key='COLUMN-Z1', vertical_alignment='center', justification='center',pad=0, expand_y = 'True'))
        last_rotator_column_list = list()
        if (distance_rotators % rotator_in_GUI) > 0:
            print_log(f'Adding rotators: {(distance_rotators // rotator_in_GUI) * rotator_in_GUI  + 1} - {distance_rotators} + {time_rotators} spinners')
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
        print_log(f'Starting GUI. trolley = {trolley_motors}, zaber ={zaber_motors}, gripper = {gripper_motors}')

        deactivateGUI(window)

        sg.PopupAnimated(image_source=gif103, text_color='blue', 
                        message='Loading...',background_color='grey', time_between_frames=100)    

        return window

    def main_loop():

    # Layout (COM / on / off)
        # layout = [
        #     [sg.Frame('', la_gripper,  expand_x=True,  relief=sg.RELIEF_GROOVE, \
        #             border_width=3, vertical_alignment='center', element_justification = "center")],
        #     [sg.Frame('', trolley,  expand_x=True,  relief=sg.RELIEF_GROOVE, \
        #             border_width=3, vertical_alignment='center', element_justification = "center")]

        # ]

        # window = sg.Window('Unitest', layout, finalize = True)

        layout = setGUI(trolley_motors)
        window = StartGUI(layout, 'UNITEST')   

        _mxdev:MAXON_Motor
        devs:MAXON_Motor.portSp = MAXON_Motor.init_devices() # default parameters
                                            # init devices and pereferials 



        down = graphic_off = True

        dev_trolley = None
        dev_gripper =  None

        for mxn_dev in devs:
            if mxn_dev.C_type == DevType.TROLLEY:
                if mxn_dev.dev_mDC:
                    dev_trolley = mxn_dev.dev_mDC 
                else: 
                    print_err(f'Unsupported TROLLEY device: {mxn_dev}') 

            elif mxn_dev.C_type == DevType.GRIPPERv3:
                if mxn_dev.dev_mDC:
                    dev_gripper = mxn_dev.dev_mDC 

                else: 
                    print_err(f'Unsupported GRIPPER device: {mxn_dev}') 

                # dev_gripper = mxn_dev.dev_mDC 

        if dev_trolley:
            dev_trolley.mDev_pressed = False

        if dev_gripper:
            dev_gripper.mDev_pressed = False
        


    #-----------------------------------------------------------   
        # if dev_trolley:
        #     window['-TROLLEY_POSSITION-'].update(value = dev_trolley.mDev_pos)
        #     window['-TROLLEY_VELOCITY-'].update(value = dev_trolley.rpm)

        while True:

            #get event
            event, values = window.read(timeout=100)

            # print(event, values)

            #When the window is closed or the Exit button is pressed
            if event in (sg.WIN_CLOSED, 'Exit'):
                print_inf(f'Exiting')
                # sys.exit()
                break


            #When '-TOGGLE-GRAPHIC-' button is presseddisab
            elif event == 'ONOFF':
                graphic_off = not graphic_off
                window['ONOFF'].update(image_data=toggle_btn_off if graphic_off else toggle_btn_on)
                if dev_gripper: 
                    if graphic_off:
                        dev_gripper.gripper_on()
                        print_log(f'Switching on')
                    else:
                        dev_gripper.gripper_off()
                        print_log(f'Switching off')

                
                window['ONOFF'].update(disabled = True)
                
                if dev_gripper:
                    dev_gripper.mDev_pressed = True

            elif  event == '-TROLLEY_TARGET-':
                if  len(values['-TROLLEY_TARGET-']) > 0 and values['-TROLLEY_TARGET-'][-1] not in ('-0123456789'):
                    sg.popup("Only digits allowed")
                    window['-TROLLEY_TARGET-'].update(values['-TROLLEY_TARGET-'][:-1])
                    # window['-TROLLEY_TARGET-'].update(disabled = True)
            elif event == '-TROLLEY_POS_SET-':
                window['-TROLLEY_POSSITION-'].update(value = values['-TROLLEY_TARGET-'])


                if dev_trolley:
                    dev_trolley.go2pos(values['-TROLLEY_TARGET-'])
                    dev_trolley.mDev_pressed = True
                
                window['-TROLLEY_POS_SET-'].update(disabled = True)
                window['-TROLLEY_RIGHT-'].update(disabled = True)
                window['-TROLLEY_LEFT-'].update(disabled = True)

            elif event == '-TROLLEY_TARGET_RESET-':
                window['-TROLLEY_POSSITION-'].update(value = 0)
                window['-TROLLEY_TARGET-'].update(value = 0) 
                if dev_trolley:
                    dev_trolley.mDev_reset_pos()
                
            elif event == '-TROLLEY_RIGHT-':
                window['-TROLLEY_POS_SET-'].update(disabled = True)
                window['-TROLLEY_RIGHT-'].update(disabled = True)
                window['-TROLLEY_LEFT-'].update(disabled = True)
                if dev_trolley:
                    dev_trolley.mDev_forward()
                    dev_trolley.mDev_pressed = True

            elif event == '-TROLLEY_LEFT-':
                window['-TROLLEY_POS_SET-'].update(disabled = True)
                window['-TROLLEY_RIGHT-'].update(disabled = True)
                window['-TROLLEY_LEFT-'].update(disabled = True)
                if dev_trolley:
                    dev_trolley.mDev_backwrd()
                    dev_trolley.mDev_pressed = True
            
            elif event == '-TROLLEY_STOP-':
                if dev_trolley:
                    dev_trolley.mDev_stop()


                window['-TROLLEY_POS_SET-'].update(disabled = False)
                window['-TROLLEY_RIGHT-'].update(disabled = False)
                window['-TROLLEY_LEFT-'].update(disabled = False)
                

            if dev_gripper  and dev_gripper.mDev_pressed and not dev_gripper.wd.is_alive():
                print_log(f'Complete')
                window['ONOFF'].update(disabled = False)
                dev_gripper.mDev_pressed = False

            if dev_trolley and dev_trolley.mDev_pressed and not dev_trolley.wd.is_alive():
                print_log(f'Trolley Complete')
                window['-TROLLEY_POS_SET-'].update(disabled = False)
                window['-TROLLEY_RIGHT-'].update(disabled = False)
                window['-TROLLEY_LEFT-'].update(disabled = False)
                dev_trolley.mDev_pressed = False
            

            if  dev_trolley and dev_trolley.mDev_pressed and dev_trolley.wd.is_alive():
                new_pos = dev_trolley.mDev_get_cur_pos()
                # print_log(f'Updating possition: {new_pos}')
                window['-TROLLEY_POSSITION-'].update(value = new_pos)

        
        if dev_trolley:
            del  dev_trolley
        if dev_gripper:
            del dev_gripper    

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