import struct
from time import sleep

# Exported
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import devStatsInfo
from backend.app.modules.sapro.src.returnTypes.MapAllStatInfo import mapInfo
from backend.app.modules.sapro.src.returnTypes.MapListInfo import MapListInfo
from backend.app.modules.sapro.src.saproException import SaproException
from backend.app.modules.sapro.src.saproFileFunctions import WriteDataIntoFile
from backend.app.modules.sapro.src.saproServerFunctions import GetTempFileName


def GetMapDevListFromServer(saproCommObj):
    """
        Sends '' command to retrieve list of all maps and running devices count from server

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c

        Args:

            saproCommObj:    An instance of SaproCommunication class.

        Returns:

            A list of objects of mapInfo class.
    """

    request = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue('PACKET_NS_GET_ALL_MAPDEVLIST_INFO'),
                                                     saproCommObj.getValue("HEADERLENGTH"))
    saproCommObj.sock.send(request, len(request))

    mapInfoList = list()

    remainingPackets = 1
    while (remainingPackets != 0 and remainingPackets != 3):
        index = 0
        replyBuf = saproCommObj.getReplyDataBuffer("GetMapDevListFromServer", \
                                                   "PACKET_NS_GET_ALL_MAPDEVLIST_INFO", \
                                                   "PACKET_NS_REPLY_OK")

        numTotalMaps = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        numMaps = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingPackets = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        i = 0
        for i in range(numMaps):
            mapNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            mapName = struct.unpack_from("%ds" % mapNameLen, replyBuf, index)[0].decode()
            index += mapNameLen

            hostNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            hostName = struct.unpack_from("%ds" % hostNameLen, replyBuf, index)[0].decode()
            index += hostNameLen

            mapPort = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numRunningDevices = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = mapInfo(mapName, hostName, \
                           mapPort, numRunningDevices)
            mapInfoList.append(info)
    printDevStatusList(mapInfoList)
    return mapInfoList


# Exported
def GetStatsFromMap(saproCommObj, mapName):
    """
        Sends 'stats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m sample.map -c stats -i 192.168.0.1

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map whose statistics is being fetched.

        Returns:

            A list of tuples. Each touple consists of a device, which is included in that map, and it's statistics.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetStatsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetStatsFromMap : Could not retrieve map info{0}".format(mapName))

    statusList = GetDeviceStatistics(saproCommObj, mapInfo.hostIdByteArray, mapInfo.mapPort, "")
    printDevStatusList(statusList)
    return statusList


def printDevStatusList(statusList):
    print("printDevStatusList : status list Len", len(statusList))
    for val in enumerate(statusList):
        print(val)


def getMapInfo(saproCommObj, mapName):
    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("getMapInfo : Map name not specified")

    mapNameLen = len(mapName)

    totalPacketLength = saproCommObj.getValue("HEADERLENGTH") + saproCommObj.getValue("SHORT_LENGTH") + mapNameLen

    headerBuffer = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GET_INFO"),
                                                          totalPacketLength)
    requestBuf = bytearray(totalPacketLength)
    index = 0
    struct.pack_into("80s", requestBuf, index, headerBuffer)
    index += struct.calcsize("80s")
    struct.pack_into(">h", requestBuf, index, mapNameLen)
    index += struct.calcsize(">h")
    struct.pack_into("%ds" % mapNameLen, requestBuf, index, mapName.encode())
    # print("getMapInfo : Request Buffer:",requestBuf)
    index += mapNameLen

    saproCommObj.sock.send(requestBuf, index)
    replyBuf = bytearray()
    replyBuf = saproCommObj.getReplyDataBuffer("getMapInfo", "PACKET_NS_GET_INFO")
    # print("getMapInfo : ReplyBuf:",replyBuf)
    index = 0
    hostIdLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    hostId = struct.unpack_from("%ds" % hostIdLen, replyBuf, index)[0].decode()
    index += hostIdLen
    portNum = struct.unpack_from(">l", replyBuf, index)[0]
    mapInfo = MapListInfo(portNum, mapName, hostId)
    print("getMapInfo :MapName-{0} portNum-{1} hostid-{2}".format(mapName, portNum, hostId))
    return (mapInfo)


# Exported
def getMapListFromServer(saproCommObj):
    """
        Sends 'maplist' command and retrieves list of running maps from the server.

        Equivalent to executing: sapcnsl -p 2100 -c maplist -i 192.168.0.1

        Args:

            saproCommObj:    An instance of SaproCommunication class.

        Returns:

            A list of objects of MapListInfo class.
    """

    packets = ()
    buf = bytearray()
    remainingPackets = 1
    numOfMaps = 0

    headerBuffer = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GET_ALL_MAPLIST_INFO"),
                                                          saproCommObj.getValue("HEADERLENGTH"))
    # print("getMapListFromServer:Request",headerBuffer)
    saproCommObj.sock.send(headerBuffer, len(headerBuffer))

    while remainingPackets != 0 and remainingPackets != 3:
        buf = saproCommObj.getReplyDataBuffer("getMapListFromServer", "PACKET_NS_GET_ALL_MAPLIST_INFO")
        if buf == None:
            return packets
        index = 0
        numOfMaps = struct.unpack_from(">l", buf, index)[0]
        index += struct.calcsize(">l")
        numOfMapsInEachPacket = struct.unpack_from(">l", buf, index)[0]
        index += struct.calcsize(">l")
        remainingPackets = struct.unpack_from(">l", buf, index)[0]
        index += struct.calcsize(">l")

        mapData = buf[index:]
        index = 0
        mapListarray = []
        for i in range(numOfMapsInEachPacket):
            print("Map", i)
            mapNameLen = struct.unpack_from(">h", mapData, index)[0]
            index += struct.calcsize(">h")
            mapName = struct.unpack_from("%ds" % mapNameLen, mapData, index)[0].decode()
            index += mapNameLen
            hostIdLen = struct.unpack_from(">h", mapData, index)[0]
            index += struct.calcsize(">h")
            str = '{0}{1}'.format(hostIdLen, 's')
            hostId = struct.unpack_from(str, mapData, index)[0]
            index += hostIdLen
            portNumber = struct.unpack_from(">l", mapData, index)[0]
            index += struct.calcsize(">l")
            mapObj = MapListInfo(portNumber, mapName, hostId)
            mapListarray.append(mapObj)

        for i in range(len(mapListarray)):
            mapObj = mapListarray[i]
            print("Map- MapName-{0},HostId-{1},Port-{2}".format(mapObj.mapName, mapObj.hostIdByteArray, mapObj.mapPort))

        return mapListarray


# Exported
def SendStopCmdToMap(saproCommObj, mapName):
    """
        Sends 'stop' command to stop specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c stop

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStopCmdToMap : Map name not specified")

    mapInfo = None
    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStopCmdToMap : Could not retrieve map info{0}".format(mapName))

    headerBuffer = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_SERVER_ASKED_TO_TERMINATE"),
                                                          saproCommObj.getValue("HEADERLENGTH"))
    if (saproCommObj.newVersion == True):
        recvBuf = saproCommObj.connectToMapAndGetResponse(headerBuffer, mapInfo.mapPort, True)
        sleep(saproCommObj.stopMapDelay)
        msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
        msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0].decode()
        return msg
    else:
        saproCommObj.connectToMapAndGetResponse(headerBuffer, mapInfo.mapPort, False)
        return "Request to stop map {0} sent".format(mapName)


# Exported
def SendStartCmdToMap(saproCommObj, mapName, logFile="", deviceList=[]):
    """
        Sends 'start' command to start specified map. This is syncronous start command. This function returns when the map is started successfully.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c syncstart

        Args:

            saproCommObj : An instance of SaproCommunication class.
            mapName      : Name of a Map, which is being started.
            logFile      : Name of the log file. This is an option argument.
            deviceList   : List of device keys. This is an optional argument.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("SendStartCmdToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStartCmdToMap : Map name not specified")

    devKeyFile = ""

    if len(deviceList) > 0:
        devKeys = '\n'.join(deviceList)

        devKeyFile = GetTempFileName(saproCommObj, "")

        if devKeyFile == "":
            raise SaproException("Unable to get temp file name from server.")

        if WriteDataIntoFile(saproCommObj, devKeyFile, devKeys) is False:
            raise SaproException("Unable to write data to file %s at server" % (devKeyFile))

    requestBuf = saproCommObj.CreateRequesttHeaderPacketForStartMapCommand("PACKET_NS_SYNCSTART_MAP", mapName, logFile,
                                                                           devKeyFile)
    saproCommObj.sock.send(requestBuf, len(requestBuf))

    recvBuf = saproCommObj.getReplyDataBuffer("SendStartCmdToMap", "PACKET_NS_SYNCSTART_MAP")
    if saproCommObj.newVersion == 0:
        return "SendStartCmdToMap : Request to start map sent"
    else:
        return recvBuf


# Exported
def SendStartCmdToMapWithLogfile(saproCommObj, mapName, logFileName):
    """
        Sends 'start' command to start specified map and logs the message of that map in the log file
        specified in 'logFile' variable. This is syncronous start command. This function returns when the map is started successfully.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -l map1.log -c syncstart

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being started.
            logFileName:     Name of a log file to write map related logs.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print(
            "SendStartCmdToMapWithLogfile : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStartCmdToMapWithLogfile : Map name not specified")

    if logFileName == "":
        print(
            "SendStartCmdToMapWithLogfile : logFileName is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStartCmdToMapWithLogfile : logFileName not specified")

    requestBuf = saproCommObj.CreateRequesttHeaderPacketForStartMapCommand("PACKET_NS_SYNCSTART_MAP", mapName,
                                                                           logFileName)
    saproCommObj.sock.send(requestBuf, len(requestBuf))

    recvBuf = saproCommObj.getReplyDataBuffer("SendStartCmdToMapWithLogfile", "PACKET_NS_SYNCSTART_MAP")
    if saproCommObj.newVersion == False:
        return "SendStartCmdToMapWithLogfile : Request to start map sent"
    else:
        return recvBuf.decode()


# Exported
def SendAsyncStartCmdToMap(saproCommObj, mapName, logFile="", deviceList=[]):
    """
        Sends 'asynchronous start' command to start specified map. This is asynchronous call.
        This will return immidiatly after sending the command.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c start

        Args:

            saproCommObj : An instance of SaproCommunication class.
            mapName      : Name of a Map, which is being started.
            logFile      : Name of the log file. This is an option argument.
            deviceList   : List of device keys. This is an optional argument.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("SendAsyncStartCmdToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendAsyncStartCmdToMap : Map name not specified")

    devKeyFile = ""

    if len(deviceList) > 0:
        devKeys = '\n'.join(deviceList)

        devKeyFile = GetTempFileName(saproCommObj, "")

        if devKeyFile == "":
            raise SaproException("Unable to get temp file name from server.")

        if WriteDataIntoFile(saproCommObj, devKeyFile, devKeys) is False:
            raise SaproException("Unable to write data to file %s at server" % (devKeyFile))

    requestBuf = saproCommObj.CreateRequesttHeaderPacketForStartMapCommand("PACKET_NS_START_MAP", mapName, logFile,
                                                                           devKeyFile)
    saproCommObj.sock.send(requestBuf, len(requestBuf))

    recvBuf = saproCommObj.getReplyDataBuffer("SendAsyncStartCmdToMap", "PACKET_NS_START_MAP")
    if saproCommObj.newVersion == False:
        return "SendAsyncStartCmdToMap : Request to start map sent"
    else:
        return recvBuf


# Exported
def SendAsyncStartCmdToMapWithLogfile(saproCommObj, mapName, logFileName):
    """
        Sends 'start' command to start specified map and logs the message of that map in the log file
        specified in 'logFile' variable. This is asynchronous call. This will return immidiatly after sending the command.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -l map1.log -c start

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being started.
            logFileName:     Name of a log file to write map related logs.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("SendAsyncStartCmdToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendAsyncStartCmdToMapWithLogfile : Map name not specified")

    if logFileName == "":
        print(
            "SendAsyncStartCmdToMap : logFileName is not specified. Please specify the logFileName and try again...\n")
        raise SaproException("SendAsyncStartCmdToMapWithLogfile : logFileName not specified")

    requestBuf = saproCommObj.CreateRequesttHeaderPacketForStartMapCommand("PACKET_NS_START_MAP", mapName, logFileName)
    saproCommObj.sock.send(requestBuf, len(requestBuf))

    recvBuf = saproCommObj.getReplyDataBuffer("SendAsyncStartCmdToMapWithLogfile", "PACKET_NS_START_MAP")
    if saproCommObj.newVersion == False:
        return "SendAsyncStartCmdToMapWithLogfile : Request to start map sent"
    else:
        return recvBuf


# Exported
def SendFastStopCmdToMap(saproCommObj, mapName):
    """
        Sends 'faststop' command to the Sapro server to stop map immediatly.

        Equivalent to executing: sapcnsl -p 2100 -c faststop -m sample.map

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("SendFastStopCmdToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendFastStopCmdToMap : Map name not specified")

    totalLength = saproCommObj.getValue("HEADERLENGTH") + saproCommObj.getValue("SHORT_LENGTH") + len(mapName)

    requestBuf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_MAP_FASTSTOP"), totalLength)

    reqBuf = bytearray(totalLength)
    index = 0
    struct.pack_into("%ds" % saproCommObj.getValue("HEADERLENGTH"), reqBuf, index, requestBuf)
    index += saproCommObj.getValue("HEADERLENGTH")
    struct.pack_into(">h", reqBuf, index, len(mapName))
    index += struct.calcsize(">h")
    struct.pack_into("%ds" % len(mapName), reqBuf, index, mapName.encode())
    index += len(mapName)

    saproCommObj.sock.send(reqBuf, index)

    recvBuf = saproCommObj.getReplyDataBuffer("SendFastStopCmdToMap", "PACKET_NS_MAP_FASTSTOP")
    index = 0
    productNameLen = struct.unpack_from(">h", recvBuf, index)[0]
    index += struct.calcsize(">h")
    productName = struct.unpack_from("%ds" % productNameLen, recvBuf, index)[0].decode()
    return productName


# Exported
def SendStopSetupScriptToMap(saproCommObj, mapName, scriptName):
    """
        Sends 'stopsetup' command to the Sapro server to stop setup script running thread.

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            scriptName:      Name of the setup script running on a map.

        Returns:

            Appropriate message returned in response by the server.
    """

    if mapName == "":
        print("SendStopSetupScriptToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStopSetupScriptToMap : Map name not specified")

    if scriptName == "":
        print("SendStopSetupScriptToMap : scriptName is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendStopSetupScriptToMap : scriptName not specified")

    mapInfo = None
    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        print("SendStopSetupScriptToMap : Could not receive map info")
        raise SaproException("SendStopSetupScriptToMap : Could not receive map info")

    scriptNameLen = len(scriptName)
    totalLength = saproCommObj.getValue("HEADERLENGTH") + saproCommObj.getValue("SHORT_LENGTH") + scriptNameLen
    buf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_ASK_SERVER_TO_STOP_SETUP"), totalLength)
    reqBuf = bytearray(totalLength)
    index = 0
    struct.pack_into("%ds" % saproCommObj.getValue("HEADERLENGTH"), reqBuf, index, buf)
    index += saproCommObj.getValue("HEADERLENGTH")
    struct.pack_into(">h", reqBuf, index, scriptNameLen)
    index += struct.calcsize(">h")
    struct.pack_into("%ds" % scriptNameLen, reqBuf, index, scriptName.encode())
    index += scriptNameLen

    recvBuf = saproCommObj.connectToMapAndGetResponse(reqBuf, mapInfo.mapPort, True)
    if (recvBuf == None) or (recvBuf == ""):
        print("SendStopSetupScriptToMap : Unable to receive response from map- {0} , port-{1}".format(mapName,
                                                                                                      mapInfo.mapPort))
        raise SaproException(
            "SendStopSetupScriptToMap : Unable to receive response from map- {0} , port-{1}".format(mapName,
                                                                                                    mapInfo.mapPort))
    msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
    msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0].decode()
    return msg


# Exported
def SendSetupScriptToMap(saproCommObj, mapName, scriptName):
    """
        Sends 'setup' command to execute 'setup.tcl' file at server.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c setup -f setup.tcl

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            scriptName:      Name of the setup script to be executed at the server.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("SendSetupScriptToMap : Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendSetupScriptToMap : Map name not specified")

    if scriptName == "":
        print("SendSetupScriptToMap : scriptName is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendSetupScriptToMap : scriptName not specified")

    mapInfo = None
    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        print("SendSetupScriptToMap : Could not receive map info")
        raise SaproException("SendSetupScriptToMap : Could not receive map info")

    scriptNameLen = len(scriptName)
    totalLength = saproCommObj.getValue("HEADERLENGTH") + saproCommObj.getValue("SHORT_LENGTH") + scriptNameLen
    buf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_ASK_SERVER_TO_SETUP"), totalLength)
    reqBuf = bytearray(totalLength)
    index = 0
    struct.pack_into("%ds" % saproCommObj.getValue("HEADERLENGTH"), reqBuf, index, buf)
    index += saproCommObj.getValue("HEADERLENGTH")
    struct.pack_into(">h", reqBuf, index, scriptNameLen)
    index += struct.calcsize(">h")
    struct.pack_into("%ds" % scriptNameLen, reqBuf, index, scriptName.encode())
    index += scriptNameLen

    recvBuf = saproCommObj.connectToMapAndGetResponse(reqBuf, mapInfo.mapPort, True)
    if (recvBuf == None) or (recvBuf == ""):
        print("SendSetupScriptToMap : Unable to receive response from map- {0} , port-{1}".format(mapName,
                                                                                                  mapInfo.mapPort))
        raise SaproException(
            "SendSetupScriptToMap : Unable to receive response from map- {0} , port-{1}".format(mapName,
                                                                                                mapInfo.mapPort))
    msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
    msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0].decode()
    return msg


def GetDeviceStatistics(saproCommObj, mapServer, mapPort, devName):
    if mapServer == "":
        print("GetDeviceStatistics : MapServer is not specified. Please specify the map server name and try again...\n")
        raise SaproException("GetDeviceStatistics : MapServer not specified")
    if mapPort == "":
        print("GetDeviceStatistics : MapServer is not specified. Please specify the map server name and try again...\n")
        raise SaproException("GetDeviceStatistics : MapServer not specified")

    requestPac = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_STATISTICS"), devName)
    devStatList = GetDeviceStatusList(saproCommObj, mapPort, requestPac)
    return (devStatList)


def GetDeviceStatusList(saproCommObj, mapPort, requestPacket):
    mapsock = saproCommObj.connectToMapPort(saproCommObj.serverIP, mapPort)

    mapsock.send(requestPacket, len(requestPacket))

    remainingDevices = 1
    index = 0
    devInfoList = list()
    while remainingDevices > 0:
        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapsock, "GetDeviceStatusList", "")
        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            devNameLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            devName = struct.unpack_from("%ds" % devNameLen, replyBuf, index)[0].decode()
            index += devNameLen

            inPackets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            getPackets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            getNextPackets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            setPackets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            getBulkPackets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTraps = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSyslog = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            devInfo = devStatsInfo(devName, inPackets, getPackets, getNextPackets, setPackets, numResponses,
                                   getBulkPackets, numTraps, numSyslog)
            devInfoList.append(devInfo)
    return devInfoList


# Exported
def GetStatsFromMapPort(saproCommObj, mapPort):
    """
        Sends 'stats' command directly on the port on which a map is listening and
        get statistics of devices running on that map.

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapPort:         port of running map.

        Returns:

            A list of tuples. Each touple consists of a device, which is included in that map, and it's statistics
    """

    if mapPort == "" or mapPort <= 0:
        print("GetStatsFromMapPort : Map Port is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetStatsFromMapPort : Map port not specified")

    statusList = GetDeviceStatistics(saproCommObj, saproCommObj.serverIP, mapPort, "")
    return statusList


# Exported
def SendAddDevCmdToMap(saproCommObj, mapName, deviceMapFile):
    """
        Sends 'adddev' command to add a new device into the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c adddev -f newdev.map

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of the a map to which a new device will be added.
            deviceMapFile:   A device file that contains a new device's definition.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendAddDevCmdToMap : Map name not specified")

    if deviceMapFile == "":
        print("deviceMapFile is not specified. Please specify the deviceMapFile and try again...\n")
        raise SaproException("SendAddDevCmdToMap : deviceMapFile not specified")

    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        raise SaproException("SendAddDevCmdToMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_ADD_DEVICE"), deviceMapFile)

    if (saproCommObj.newVersion == True):
        recvBuf = saproCommObj.connectToMapAndGetResponse(request, mapInfo.mapPort, True)
        msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
        msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0].decode()
        return (msg)
    else:
        saproCommObj.connectToMapAndGetResponse(request, mapInfo.mapPort, False)
        return ("Request to add device sent.")


# Exported
def SendDeleteDevCmdToMap(saproCommObj, mapName, deviceMapFile):
    """
        Sends 'deldev' command to delete a device from the specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c deldev -d 192.168.0.1

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of the a map from which a device will be deleted.
            deviceMapFile:   A device name to be deleted.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendDeleteDevCmdToMap : Map name not specified")

    if deviceMapFile == "":
        print("deviceMapFile is not specified. Please specify the deviceMapFile and try again...\n")
        raise SaproException("SendDeleteDevCmdToMap : deviceMapFile not specified")

    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        raise SaproException("SendDeleteDevCmdToMap : Could not retrieve map info{0}".format(mapName))
    request = saproCommObj.CreateRequestHeaderPacketForDevString("PACKET_FROM_MAP_MGR_TO_DELETE_DEVICE", deviceMapFile)

    if (saproCommObj.newVersion == True):
        recvBuf = saproCommObj.connectToMapAndGetResponse(request, mapInfo.mapPort, True)
        msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
        msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0].decode()
        return (msg)
    else:
        saproCommObj.connectToMapAndGetResponse(request, mapInfo.mapPort, False)
        return ("Request to delete device failed..")


# Exported
def SendScenarioFileToMap(saproCommObj, mapName, scenarioFileName):
    """
    Sends 'scenario' command for a specified map with extra arguments.

    Equivalent to executing: sapcnsl -p 2100 -m map1.map -c scenario -f tclfile.tcl

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map for which scenario command is being carried out.
            scenarioFileName:Name of a scenario file to be executed for the specified map.


        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendScenarioFileToMap : Map name not specified")

    if scenarioFileName == "":
        print("scenarioFileName is not specified. Please specify the scenarioFileName and try again...\n")
        raise SaproException("SendScenarioFileToMap : scenarioFileName not specified")

    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        raise SaproException("SendScenarioFileToMap : Could not retrieve map info{0}".format(mapName))

    ret = saproCommObj.SendScenarioFile(mapInfo.hostIdByteArray, mapInfo.mapPort, scenarioFileName, "", "")
    return (ret)


# Exported
def SendScenarioFileToMapWithArgumnets(saproCommObj, mapName, scenarioFileName, args=""):
    """
    Sends 'scenario' command for a specified map with extra arguments.

    Equivalent to executing: sapcnsl -p 2100 -m map1.map -c scenario -f tclfile.tcl

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a map for which scenario command is being carried out.
            scenarioFileName:Name of a scenario file to be executed for the specified map.
            args:            This can be optional. If command requires arguments then user can specify them here.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("SendScenarioFileToMapWithArgumnets : Map name not specified")

    if scenarioFileName == "":
        print("scenarioFileName is not specified. Please specify the scenarioFileName and try again...\n")
        raise SaproException("SendScenarioFileToMapWithArgumnets : scenarioFileName not specified")

    mapInfo = getMapInfo(saproCommObj, mapName)
    if mapInfo == None:
        raise SaproException("SendScenarioFileToMapWithArgumnets : Could not retrieve map info{0}".format(mapName))

    ret = saproCommObj.SendScenarioFile(mapInfo.hostIdByteArray, mapInfo.mapPort, scenarioFileName, "", args)
    return (ret)
