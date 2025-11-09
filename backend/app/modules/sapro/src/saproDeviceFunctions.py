import os
import struct
import re
from backend.app.modules.sapro.src.saproException import SaproException
import backend.app.modules.sapro.src.saproMapFunctions as MAPFUNC
from backend.app.modules.sapro.src.returnTypes.DeviceInfo import DeviceInfo
from backend.app.modules.sapro.src.returnTypes.DeviceInfo import DeviceTagInfo
from backend.app.modules.sapro.src.returnTypes.DeviceInfo import FoundDeviceInfo
from backend.app.modules.sapro.src.returnTypes.DeviceInfo import NetFlowStats


def printDevList(devList):
    print("printDevList : Dev list Len", len(devList))
    for val in devList:
        print(val.devName)  # ,val.devStatus)


# exported
def GetDeviceStatusFromMap(saproCommObj, mapName, devName):
    """
        Sends '' command to retrieve list of devices of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map for which the list of devices will be retrieved.
            deviceName:         Name of a device for which statistics will be retrieved.

        Returns:

            A list of objects of devStatsInfo class.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetDeviceStatusFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetDeviceStatusFromMap : Map name not specified")
    if devName == "":
        print("Map name is not specified. Please specify the devName and try again...\n")
        raise SaproException("GetDeviceStatusFromMap : devName not specified")
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    statusList = MAPFUNC.GetDeviceStatistics(saproCommObj, mapInfo.hostIdByteArray, mapInfo.mapPort, devName)
    MAPFUNC.printDevStatusList(statusList)
    return statusList


def GetDeviceListOfMap(saproCommObj, mapPort):
    headerBuffer = saproCommObj.createRequestHeaderPacket(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_DEVLIST_STATUS"), saproCommObj.getValue("HEADERLENGTH"))
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapPort)
    mapSock.send(headerBuffer, len(headerBuffer))
    devList = list()
    continueLoop = 1
    index = 0
    while continueLoop == 1:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "GetDeviceListOfMap",
                                                              "PACKET_FROM_MAP_MGR_TO_GET_DEVLIST_STATUS",
                                                              "PACKET_DEVLIST_RETURNED_FROM_SERVER")
        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")
        remainingPackets = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        if (remainingPackets == 0) or (remainingPackets == 3):
            continueLoop = 0

        while numDevices > 0:

            devStatus = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            devNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            devName = struct.unpack_from("%ds" % devNameLen, replyBuf, index)[0].decode()
            index += devNameLen

            port = 0
            reCompiledVar = re.compile("^([1-9][^\/]*)\/\/(.*)$")
            isMatched = reCompiledVar.match(devName)

            if isMatched:
                devName = isMatched.group(1)
                port = isMatched.group(2)

            devInfo = DeviceInfo(devName, devStatus, port)
            devList.append(devInfo)
            numDevices -= 1

    mapSock.close()
    printDevList(devList)
    return devList


# Exported
def GetDevListFromMap(saproCommObj, mapName):
    """
        Sends 'devlist' command to retrieve list of devices of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c devlist

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map for which the list of devices will be retrieved.

        Returns:

            A list of objects of DeviceInfo class.
        """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetDevListFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetDevListFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetDevListFromMap : Could not retrieve map info{0}".format(mapName))

    devList = GetDeviceListOfMap(saproCommObj, mapInfo.mapPort)
    return devList


# Exported
def GetDevListFromMapPort(saproCommObj, mapPort):
    """
        Sends 'devlist' command to retrieve list of devices of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c devlist

        Args:

            saproCommObj:   An instance of SaproCommunication class.
            mapPort:        Port number a Map for which the list of devices will be retrieved.

        Returns:

            A list of objects of DeviceInfo class.
        """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetDevListFromMapPort : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapPort == "" or mapPort <= 0:
        print("mapPort is not specified. Please specify the map port and try again...\n")
        raise SaproException("GetDevListFromMapPort : Map port not specified")

    devList = GetDeviceListOfMap(saproCommObj, mapPort)
    return devList


# Exported
def SendStartCmdToDevice(saproCommObj, mapName, devName):
    """
        Sends 'startdev' command to start the specified device of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m sample.map -c startdev -d 192.168.16.10

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            devName:         Name of a device to be stared.

        Returns:

            An appropriate message whether the command could be sent or not.
        """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendStartCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (mapName == ""):
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if (devName == ""):
        print("Device's name is not specified. Please specify the device's name and try again...\n")
        raise SaproException("Device's name is not specified. Please specify the device's name and try again...")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("SendStartCmdToDevice : Could not retrieve map info{0}".format(mapName))

    reqPacket = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_START_DEVICE"), devName)
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapInfo.mapPort)
    mapSock.send(reqPacket, len(reqPacket))

    if (saproCommObj.newVersion is False):
        return "Request to start device sent."

    replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "SendStartCmdToDevice", "")
    index = 0
    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = ""
    if (msgLen > 0):
        msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()

    return msg


# Exported
def SendStopCmdToDevice(saproCommObj, mapName, devName):
    """
        Sends 'stopdev' command to stop the specified device of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m sample.map -c stopdev -d 192.168.16.10

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            devName:         Name of a device to be stopped.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendStopCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (mapName == ""):
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if (devName == ""):
        print("Device's name is not specified. Please specify the device's name and try again...\n")
        raise SaproException("Device's name is not specified. Please specify the device's name and try again...")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("SendStopCmdToDevice : Could not retrieve map info{0}".format(mapName))

    reqPacket = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_STOP_DEVICE"), devName)
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapInfo.mapPort)
    mapSock.send(reqPacket, len(reqPacket))

    if (saproCommObj.newVersion is False):
        return "Request to start device sent."

    replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "SendStopCmdToDevice", "")
    index = 0
    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = ""
    if (msgLen > 0):
        msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()

    return msg


# Exported
def SendRestartCmdToDevice(saproCommObj, mapName, devName):
    """
        Sends 'restartdev' command to restart the specified device of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c restartdev -d 192.128.100.1

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            devName:         Name of a device to be restarted.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendRestartCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (mapName == ""):
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if (devName == ""):
        print("Device's name is not specified. Please specify the device's name and try again...\n")
        raise SaproException("Device's name is not specified. Please specify the device's name and try again...")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("SendRestartCmdToDevice : Could not retrieve map info{0}".format(mapName))

    reqPacket = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_RESTART_DEVICE"), devName)
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapInfo.mapPort)
    mapSock.send(reqPacket, len(reqPacket))

    if (saproCommObj.newVersion is False):
        return "Request to start device sent."

    replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "SendRestartCmdToDevice", "")
    index = 0
    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = ""
    if (msgLen > 0):
        msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()

    return msg


# Exported
def FindDevice(saproCommObj, devName, mapPrefix=""):
    """
        This function takes device name and map prefix as input parameters and serches this device
        for all maps ruuning on Sapro server. The second parameter mapPrefix is optional. If specified
        then it seraches the map having the specified prefix and immidiatly returns a list of
        objects of FoundDeviceInfo class that conains this only map.

        Equivalent to executing: sapcnsl -p 2100 -d 192.168.0.1

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            devName:         Device name to be searched.

        Returns:

            A list of objects of FoundDeviceInfo class.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "FindDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (devName == ""):
        print("Device's name is not specified. Please specify the device's name and try again...\n")
        raise SaproException("Device's name is not specified. Please specify the device's name and try again...")

    mapList = MAPFUNC.getMapListFromServer(saproCommObj)
    foundDeviceList = list()

    for mapInfo in mapList:
        reqPacket = saproCommObj.CreateRequestHeaderPacketForDevString(
            saproCommObj.getValue("PACKET_ASK_MAP_MGR_TO_FIND_DEVICE"), devName)
        replyBuf = saproCommObj.connectToMapAndGetResponse(reqPacket, mapInfo.mapPort, True,
                                                           "PACKET_ASK_DEVLIST_RETURNED_FROM_SERVER")

        index = 0
        devStatus = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        mapStrLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        mapName = struct.unpack_from("%ds" % mapStrLen, replyBuf, index)[0].decode()
        index += mapStrLen

        print("MAP NAME:", mapName, mapStrLen)
        if mapName != "":
            foundDevice = FoundDeviceInfo(mapName, devName, devStatus)
            if mapPrefix != "" and re.search(mapPrefix, mapName):
                foundDeviceList.clear()
            foundDeviceList.append(foundDevice)

    printDevList(foundDeviceList)
    return foundDeviceList


def GetTagDeviceList(saproCommObj, mapPort):
    headerBuffer = saproCommObj.createRequestHeaderPacket(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_TAGDEVLIST_STATUS"), saproCommObj.getValue("HEADERLENGTH"))
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapPort)
    mapSock.send(headerBuffer, len(headerBuffer))
    devList = list()
    continueLoop = 1
    index = 0
    while continueLoop == 1:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "GetDeviceListOfMap",
                                                              "PACKET_FROM_MAP_MGR_TO_GET_DEVLIST_STATUS",
                                                              "PACKET_TAGDEVLIST_RETURNED_FROM_SERVER")
        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")
        remainingPackets = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        if (remainingPackets == 0) or (remainingPackets == 3):
            continueLoop = 0

        while numDevices > 0:
            devStatus = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            devNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            devName = struct.unpack_from("%ds" % devNameLen, replyBuf, index)[0].decode()
            index += devNameLen

            devTagLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            devTag = struct.unpack_from("%ds" % devTagLen, replyBuf, index)[0].decode()
            index += devTagLen

            devTagInfo = DeviceTagInfo(devName, devStatus, devTag)
            devList.append(devTagInfo)
            numDevices -= 1

    mapSock.close()
    printDevList(devList)

    return devList


# Exported
def GetTagDeviceListInfo(saproCommObj, mapName):
    """
        Sends 'devinfolist' command to retrieve list of devices. Each device from list contains
        device's ip address and port string, it's display tag and runing status.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c devlistinfo

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map for which the list of devices will be retrieved.

        Returns:

            A list of objects of DeviceTagInfo. Each object contains the information, such as
            device's ip and port string, display tag and status.
            Empty list if any error occured or no device is running on the map.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetTagDeviceListInfo : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetDevListFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetDevListFromMap : Could not retrieve map info{0}".format(mapName))

    devList = GetTagDeviceList(saproCommObj, mapInfo.mapPort)
    return devList


# Exported
def GetTagDeviceListInfoFromMapPort(saproCommObj, mapPort):
    """
        Sends 'devinfolist' command directly on the port of a running map and retrieve list of devices.
        Each device from list contains device's ip address and port string, it's display tag and runing status.

        Equivalent to executing: sapcnsl -p 31242 -t map -m map1.map -c devlistinfo

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapPort:         Port of a running Map for which the list of devices will be retrieved.

        Returns:

            A list of objects of DeviceTagInfo. Each object contains the information, such as
            device's ip and port string, display tag and status.
            Empty list if any error occured or no device is running on the map.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetTagDeviceListInfoFromMapPort : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapPort == "" or mapPort <= 0:
        print("mapPort is not specified. Please specify the map port and try again...\n")
        raise SaproException("GetTagDeviceListInfoFromMapPort : Map port not specified")

    devList = GetTagDeviceList(saproCommObj, mapPort)
    return devList


# Exported
def SendScenarioCmdToDevice(saproCommObj, mapName, devName, scenarioFile, args=""):
    """
        Sends 'scenario' command to the specified device of the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c scenario -d 192.168.128.100 -f tclfile.tcl -a

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            deviceName:      Name of a device for which scenario file will be executed.
            scenarioFile:    File to be executed for the specified device.
            args:            Scenario command arguments, which can be optional.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendScenarioCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if scenarioFile == "":
        print("Scenario file is not specified. Please specify the Scenario file and try again...\n")
        raise SaproException("Scenario file is not specified. Please specify the Scenario file and try again...")

    if devName == "":
        print("devName is not specified. Please specify the devName and try again...\n")
        raise SaproException("devName is not specified. Please specify the devName and try again...")

    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        raise SaproException("SendScenarioFileToMap : Could not retrieve map info{0}".format(mapName))

    ret = saproCommObj.SendScenarioFile(mapInfo.hostIdByteArray, mapInfo.mapPort, scenarioFile, devName, args)
    return (ret)


# Exported
def SendTclCmdToDevice(saproCommObj, mapName, devName, cmd, args=""):
    """
        Sends 'tcl' command for a specified map to carry out built in tcl command on a specified device.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c tcl -d 192.128.100.1 -s "SA_disableping"

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device..
            deviceName:      Name of the device for which tcl command will be executed.
            cmd:             Tcl command to be executed for the specified device.
            args:            This is an optional argument. If cmd has command line options, you can specify here.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendTclCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if cmd == "":
        print("cmd is not specified. Please specify the TCL cmd and try again...\n")
        raise SaproException("cmd is not specified. Please specify the TCL cmd and try again...")

    if devName == "":
        print("Device name is not specified. Please specify device's name and try again...\n")
        raise SaproException("Device name is not specified. Please specify device's name and try again...")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("SendTclCmdToDevice : Could not retrieve map info{0}".format(mapName))

    if args != "":
        reqPacket = saproCommObj.CreateRequestHeaderPacketForCommand(
            saproCommObj.getValue("PACKET_ASK_SERVER_TO_EVAL_DEV_TCL_ARGS"), devName, cmd, args)
    else:
        reqPacket = saproCommObj.CreateRequestHeaderPacketForCommand(
            saproCommObj.getValue("PACKET_ASK_SERVER_TO_EVAL_DEV_TCL"), devName, cmd, args)

    replyBuf = saproCommObj.connectToMapAndGetResponse(reqPacket, mapInfo.mapPort, True)

    index = 0
    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    if msgLen <= 0:
        return "TCl command has been sent.."

    msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()
    return msg


# Exported
def SendSetVarTclCmdToDevice(saproCommObj, mapName, devName, varOid, varType, varVal):
    """
        Sends 'tcl' command to set the SNMP variable, whose OID is varOid, type is varType and
        value is varVal, on the device devName.

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            deviceName:      Name of the device for which tcl command will be executed.
            varOid:          SNMP OID of the variable tobe set.
            varType:         Data type of the above variable.
            varVal:          Value tobe set to SNMP variable.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendSetVarTclCmdToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if devName == "":
        return "Device's name is not specified. Please specify the device's name and try again...\n"

    if varOid == "":
        return "Variable's OID is not specified. Please specify the Variable's OID and try again...\n"

    if varType == "":
        return "Variable's data type is not specified. Please specify the Variable's data type and try again...\n"

    if varVal == "":
        return "Variable's value is not specified. Please specify the Variable's value and try again...\n"

    tclCmd = "if [ catch { SA_setvar [list [list VAROID VARTYPE VARVAL]]} res] { SA_setvaltype [list [list VAROID VARTYPE fixed(VARVAL)]] }"

    tclCmd = tclCmd.replace("VAROID", varOid)
    tclCmd = tclCmd.replace("VARTYPE", varType)
    tclCmd = tclCmd.replace("VARVAL", varVal)

    return SendTclCmdToDevice(saproCommObj, mapName, devName, tclCmd)


# Exported
def SendTclFileWithArgsToDevice(saproCommObj, mapName, devName, tclFile, args):
    """
        Opens the specified tcl file and club all the commands into single tcl commands. Sends this tcl command with specified
        tcl command arguments for a specified map on a specified device.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c tcl -d 192.168.10.10 -f "sendtraps.tcl"  -a "arg1, agr2, ..."

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device..
            deviceName:      Name of the device for which tcl command will be executed.
            tclFile:         Tcl file containig tcl commands to be executed for the specified device.
            args:            TCL command arguments.

        Returns:

            An appropriate message whether the command could be sent or not.
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "SendTclFileWithArgsToDevice : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("Map name is not specified. Please specify the map name and try again...")

    if devName == "":
        print("Device's name is not specified. Please specify the device's name and try again...\n")
        raise SaproException("Device's name is not specified. Please specify the device's name and try again...")

    if tclFile == "":
        print("tclFile is not specified. Please specify the TCL file and try again...\n")
        raise SaproException("TCL file is not specified. Please specify the TCL file and try again...")

    fileContents = ""
    if os.path.exists(tclFile):
        with open(tclFile, 'r') as fp:
            try:
                fileContents = fp.read()
            except IOError as err:
                raise SaproException(format(err))
    if args != "":
        args = ' '.join('"{}"'.format(word) for word in args.split(','))

    return SendTclCmdToDevice(saproCommObj, mapName, devName, fileContents, args)


def GetNetflowStatistics(saproCommObj, mapPort, devName):
    reqPacket = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_NETFLOW_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapPort)
    mapSock.send(reqPacket, len(reqPacket))
    devList = list()
    continueLoop = 1
    index = 0
    while continueLoop == 1:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, "GetDeviceListOfMap",
                                                              "PACKET_FROM_MAP_MGR_TO_GET_NETFLOW_STATISTICS",
                                                              "PACKET_NETFLOW_STATISTICS_RETURNED_FROM_SERVER")
        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")
        remainingPackets = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        if (remainingPackets == 0) or (remainingPackets == 3):
            continueLoop = 0

        while numDevices > 0:
            devNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            devName = struct.unpack_from("%ds" % devNameLen, replyBuf, index)[0].decode()
            index += devNameLen

            pktCnt = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            netFlowFlow = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            devInfo = NetFlowStats(devName, pktCnt, netFlowFlow)
            devList.append(devInfo)
            numDevices -= 1

    mapSock.close()
    return devList


# Exported
def GetDeviceNetflowStatFromMap(saproCommObj, mapName, devName=""):
    """
        Gives the netflow statistics of the specified map. devName is optional.
        If devName is given then netflow statistics of that device will be returned
        otherwise statistics for all devices of that map will be returned.

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map that contains specified device.
            deviceName:      Name of the device.

        Returns:

            A list of objects of NetFlowStats class.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetDeviceNetflowStatFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetDeviceNetflowStatFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetDeviceNetflowStatFromMap : Could not retrieve map info{0}".format(mapName))

    devList = GetNetflowStatistics(saproCommObj, mapInfo.mapPort, devName)
    printDevList(devList)
    return devList
