

from operator import itemgetter

ErrCodes = [
    {'code' : 0x00000000 , 'txt' : 'No error Communication was successful'},  
    {'code' : 0x05030000 , 'txt' : 'Toggle error Toggle bit not alternated'},
    {'code' : 0x05040000 , 'txt' :'SDO timeout SDO protocol timed out'},
    {'code' : 0x05040001 , 'txt' :'Client/server specifier error Client/server command specifier not valid or unknown'},
    {'code' : 0x05040002 , 'txt' :'Invalid block size Invalid block size (block mode only) '},
    {'code' : 0x05040003 , 'txt' :'Invalid sequence Invalid sequence number (block mode only) '},
    {'code' : 0x05040004 , 'txt' :'CRC error CRC error (block mode only) '},
    {'code' : 0x05040005 , 'txt' :'Out of memory error Out of memory'},
    {'code' : 0x06010000 , 'txt' :'Access error Unsupported access to an object (e.g. write command to a read-only object) '},
    {'code' : 0x06010001 , 'txt' :'Write only Read command to a write only object'},
    {'code' : 0x06010002 , 'txt' :'Read only Write command to a read only object'},
    {'code' : 0x06020000 , 'txt' :'Object does not exist Last read or write command had a wrong object index or subindex'},
    {'code' : 0x06040041 , 'txt' :'PDO mapping error Object cannot be mapped to PDO'},
    {'code' : 0x06040042 , 'txt' :'PDO length error Number and length of objects to be mapped would exceed PDO length'},
    {'code' : 0x06040043 , 'txt' :'General parameter error General parameter incompatibility'},
    {'code' : 0x06040047 , 'txt' :'General internal Incompatibility error General internal incompatibility in device'},
    {'code' : 0x06060000 , 'txt' :'Hardware error Access failed due to a hardware error'},
    {'code' : 0x06070010 , 'txt' :'Service parameter error Data type does not match, length or service parameter does not match'},
    {'code' : 0x06070012 , 'txt' :'Service parameter too high Data type does not match, length or service parameter too high'},
    {'code' : 0x06070013 , 'txt' :'Service Parameter too low Data type does not match, length or service parameter too low'},
    {'code' : 0x06090011 , 'txt' :'Object subindex error Last read or write command had a wrong subindex'},
    {'code' : 0x06090030 , 'txt' :'Value range error Value range of parameter exceeded'},
    {'code' : 0x06090031 , 'txt' :'Value too high Value of parameter written too high'},
    {'code' : 0x06090032 , 'txt' :'Value too low Value of parameter written too low'},
    {'code' : 0x06090036 , 'txt' :'Maximum less minimum error Maximum value is less than minimum value'},
    {'code' : 0x08000000 , 'txt' :'General error General error'},
    {'code' : 0x08000020 , 'txt' :'Transfer or store error Data cannot be transferred or stored'},
    {'code' : 0x08000021 , 'txt' :'Local control error Data cannot be transferred or stored to application because of local control'},
    {'code' : 0x08000022 , 'txt' :'Wrong device state Data cannot be transferred or stored to application because of present device state'},
    {'code' : 0x0F00FFB9 , 'txt' :'CAN ID error Wrong CAN ID'},
    {'code' : 0x0F00FFBC, 'txt' :'Service mode error Device is not in service mode'},
    {'code' : 0x0F00FFBE, 'txt' :' Password error Password is wrong'},
    {'code' : 0x0F00FFBF, 'txt' :' Illegal command RS232 , command is illegal (does not exist) '},
    {'code' : 0x0F00FFC0 , 'txt' :'Wrong NMT state Device is in wrong NMT state'},

    {'code' : 0x00000000, 'txt' : ' No error Communication was successful'},
    {'code' : 0x10000001, 'txt' : ' Internal error Internal error'},
    {'code' : 0x10000002, 'txt' : ' Null pointer Null pointer passed to function'},
    {'code' : 0x10000003, 'txt' : ' Handle not valid Handle passed to function is not valid'},
    {'code' : 0x10000004, 'txt' : ' Bad virtual device name Virtual device name is not valid'},
    {'code' : 0x10000005, 'txt' : ' Bad device name Device name is not valid'},
    {'code' : 0x10000006, 'txt' : ' Bad protocol stack name Protocol stack name is not valid'},
    {'code' : 0x10000007, 'txt' : ' Bad interface name Interface name is not valid'},
    {'code' : 0x10000008, 'txt' : ' Bad port name Port is not valid'},
    {'code' : 0x10000009, 'txt' : ' Library not loaded Could not load external library'},
    {'code' : 0x1000000A, 'txt' : ' Command failed Error while executing command'},
    {'code' : 0x1000000B, 'txt' : ' Timeout Timeout occurred during execution'},
    {'code' : 0x1000000C, 'txt' : ' Bad parameter Bad parameter passed to function'},
    {'code' : 0x1000000D, 'txt' : ' Command aborted by user Command was aborted by user'},
    {'code' : 0x1000000E, 'txt' : ' Buffer too small Buffer is too small'},
    {'code' : 0x1000000F, 'txt' : ' No communication found No communication settings found'},
    {'code' : 0x10000010, 'txt' : ' Function not supported Function is not supported'},
    {'code' : 0x10000011, 'txt' : ' Parameter already used Parameter is already in use'},
    {'code' : 0x10000013, 'txt' : ' Bad device handle Bad device handle'},
    {'code' : 0x10000014, 'txt' : ' Bad protocol stack handle Bad protocol stack handle'},
    {'code' : 0x10000015, 'txt' : ' Bad interface handle Bad interface handle'},
    {'code' : 0x10000016, 'txt' : ' Bad port handle Bad port handle'},
    {'code' : 0x10000017, 'txt' : ' Address parameters are not correct Address parameters are not correct'},
    {'code' : 0x10000020, 'txt' : ' Bad device state Bad device state'},
    {'code' : 0x10000021, 'txt' : ' Bad file content Bad file content'},
    {'code' : 0x10000022, 'txt' : ' Path does not exist System cannot find specified path'},
    {'code' : 0x10000024, 'txt' : ' Cross thread error (.NET only) Open device and close device called from different threads'},
    {'code' : 0x10000026, 'txt' : ' Gateway support error Gateway is not supported'},
    {'code' : 0x10000027, 'txt' : ' Serial number update error Serial number update failed'},
    {'code' : 0x10000028, 'txt' : ' Communication interface error Communication interface is not supported'},
    {'code' : 0x10000029, 'txt' : ' Firmware support error Firmware version does not support functionality'},
    {'code' : 0x1000002A, 'txt' : ' Firmware file hardware error Firmware file does not match hardware version'},
    {'code' : 0x1000002B, 'txt' : ' Firmware file error Firmware file does not match or is corrupt'},
    {'code' : 0x1000002C, 'txt' : ' Parameter access denied Parameter access denied'},
    {'code' : 0x1000002D, 'txt' : ' Data recorder not configured Data recorder not configured'},
    {'code' : 0x1000002E, 'txt' : ' File format not supported File format not supported'},
    {'code' : 0x1000002F, 'txt' : ' Failed saving data Failed saving data'},

    {'code' : 0x20000001, 'txt' : ' Opening interface error Error while opening interface'},
    {'code' : 0x20000002, 'txt' : ' Closing Interface error Error while closing interface'},
    {'code' : 0x20000003, 'txt' : ' Interface is not open Interface is not open'},
    {'code' : 0x20000004, 'txt' : ' Opening port error Error while opening port'},
    {'code' : 0x20000005, 'txt' : ' Closing port error Error while closing port'},
    {'code' : 0x20000006, 'txt' : ' Port is not open Port is not open'},
    {'code' : 0x20000007, 'txt' : ' Resetting port error Error while resetting port'},
    {'code' : 0x20000008, 'txt' : ' Configuring port settings error Error while configuring port settings'},
    {'code' : 0x20000009, 'txt' : ' Configuring port mode error Error while configuring port mode'},
    {'code' : 0x2000000A, 'txt' : ' Getting port settings error Error while getting port settings'},
    {'code' : 0x2000000B, 'txt' : ' Access denied Access denied error'},

    {'code' : 0x51000001, 'txt' : ' Bad data size received Object data size does not correspond to requested data size'},
    {'code' : 0x51000002, 'txt' : ' Homing error Homing procedure failed'},
    {'code' : 0x51000007, 'txt' : ' Sensor configuration not supported Sensor configuration cannot be written to controller'},
    {'code' : 0x51000008, 'txt' : ' Sensor configuration unknown Sensor configuration read from controller is not supported by library'},
    {'code' : 0x51000009, 'txt' : ' Configuration not supported Configuration is not supported'},
    {'code' : 0x5100000A, 'txt' : ' Digital input mask not supported Digital input mask is not supported'},
    {'code' : 0x5100000B, 'txt' : ' Controller gain not supported Tuning mode does not support the gain'},


    
]



ErrTxt = lambda errC : ErrCodes[list(map(itemgetter('code'), ErrCodes)).index (errC)]['txt'] if errC in  list(map(itemgetter('code'), ErrCodes))  else 'Unknown error'

if __name__ == "__main__":


    keyVal  = 0x51000008
    keyVal  = 0x06010000
    # test_list = list(map(itemgetter('code'), ErrCodes))
    # print (f'test_list = \n {test_list}')
    # if 0x51000008 in list(map(itemgetter('code'), ErrCodes)):
    #     print (test_list.index (keyVal))
    # i_ind = test_list.index (keyVal)
    # print (f'i_ind = {i_ind}')
    # print (f'err_msg =  {ErrCodes[i_ind]["txt"]}')

    print (f'{keyVal} = {ErrTxt(keyVal)} ')