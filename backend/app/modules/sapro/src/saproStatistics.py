import struct

import backend.app.modules.sapro.src.saproMapFunctions as MAPFUNC
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import allIOTStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import allProtocolStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import bacnetStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import coapStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import devNetflowinfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import httpCLStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import modbusStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import mqttSNStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import mqttUserStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import perfStatInfo
from backend.app.modules.sapro.src.returnTypes.DeviceStatsInfo import telnetSSHTL1StatsInfo
from backend.app.modules.sapro.src.saproException import SaproException


# tested
def GetTelnetSshTl1StatisticsFromMap(saproCommObj, mapName, devName=""):
    """
        Sends 'telStats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c sshstats -d deviceName
        sapcnsl -p 2100 -m map1.map -c telstats -d deviceName

        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            deviceName:      Name of a telnet device whose statistics is being fetched.

        Returns:

            List of Telnettstats object if statistics of telnet devices are available
    			otherwise returns an empty list.
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetTelnetSshTl1StatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetTelnetSshTl1StatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetTelnetSshTl1StatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_TELNET_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    telnetSSHTL1StatsInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0
        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetTelnetSshTl1StatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_TELNET_STATISTICS", \
                                                              "PACKET_TELNET_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        i = 0
        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numActiveTelnetSessionsPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTelnetSessionsPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTelnetCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSSHSessionsPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSSHCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTL1SessionsPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTL1CmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNetFlowSentPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = telnetSSHTL1StatsInfo(deviceNameStr, numActiveTelnetSessionsPkts, \
                                         numTelnetSessionsPkts, numTelnetCmdPkts, numSSHSessionsPkts, \
                                         numSSHCmdPkts, numTL1SessionsPkts, numTL1CmdPkts, numNetFlowSentPkts)
            telnetSSHTL1StatsInfoList.append(info)
    # MAPFUNC.printDevStatusList(telnetSSHTL1StatsInfoList)
    return telnetSSHTL1StatsInfoList


# tested
def GetMqttStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
        Sends 'mqttStats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c mqttstats -d deviceName


        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            deviceName:      Name of a telnet device whose statistics is being fetched.

        Returns:

            List of MqttSnstats object if statistics of Mqtt devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetMqttStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetMqttStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetMqttStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_MQTT_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    mqttStatList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0
        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetMqttStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_MQTT_STATISTICS", \
                                                              "PACKET_MQTT_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numPublishes = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numPings = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numRetries = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAcks = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAvgLatency = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = devNetflowinfo(deviceNameStr, numPublishes, \
                                  numPings, numRetries, \
                                  numAcks, numAvgLatency)
            mqttStatList.append(info)
    ##MAPFUNC.printDevStatusList(mqttStatList)
    return mqttStatList


# exported
def GetHttpCLStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
        Sends 'httpclstats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c httpclstats -d deviceName


        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            deviceName:      Name of a telnet device whose statistics is being fetched.

        Returns:

            List of HttpStat object if statistics of http devices are available
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetHttpCLStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetHttpCLStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetHttpCLStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_HTTPCL_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    httpCLStatList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0
        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetHttpCLStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_HTTPCL_STATISTICS", \
                                                              "PACKET_HTTPCL_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numTotalRequests = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTotalResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = httpCLStatInfo(deviceNameStr, numTotalRequests, \
                                  numTotalResponses)
            httpCLStatList.append(info)
    # MAPFUNC.printDevStatusList(httpCLStatList)
    return httpCLStatList


# Tested
def GetBacnetStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
        Sends 'bacnetstats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c bacnetstats -d deviceName


        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            deviceName:      Name of a telnet device whose statistics is being fetched.

        Returns:

            List of BacnetStat object if statistics of bacnet devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetBacnetStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetBacnetStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetBacnetStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_BACNET_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    bacnetStatList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0
        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetBacnetStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_BACNET_STATISTICS", \
                                                              "PACKET_BACNET_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        i = 0
        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numTotalRequests = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTotalResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = bacnetStatInfo(deviceNameStr, numTotalRequests, \
                                  numTotalResponses)
            bacnetStatList.append(info)
    ##MAPFUNC.printDevStatusList(bacnetStatList)
    return bacnetStatList


# Tested
def GetCoapStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
        Sends 'coapstats' command to get statistics of a specified map.

        Equivalent to executing: sapcnsl -p 2100 -m map1.map -c coapstats -d deviceName


        Args:

            saproCommObj:    An instance of SaproCommunication class.
            mapName:         Name of a Map, which is being stopped.
            deviceName:      Name of a telnet device whose statistics is being fetched.

        Returns:

            List of COAPStat object if statistics of coap devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetCoapStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetCoapStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetCoapStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_COAP_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    coapStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetCoapStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_COAP_STATISTICS", \
                                                              "PACKET_COAP_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        i = 0
        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numTotalRequests = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTotalResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numGets = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numPosts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numPuts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numDeletes = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNotifications = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = coapStatInfo(deviceNameStr, numTotalRequests, \
                                numTotalResponses, numGets, \
                                numPosts, numPuts, \
                                numDeletes, numNotifications)
            coapStatInfoList.append(info)

    # MAPFUNC.printDevStatusList(coapStatInfoList)
    return coapStatInfoList


# Tested
def GetMqttSNStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'mqttsnstat' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c mqttsnstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of MQTTSNstat object if statistics of mqttsn devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetMqttSNStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetMqttSNStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetMqttSNStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_MQTT_SN_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    mqttSNStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetMqttSNStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_MQTT_SN_STATISTICS", \
                                                              "PACKET_MQTT_SN_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numPublishes = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numPings = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numRetries = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAcks = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAvgLatency = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = mqttSNStatInfo(deviceNameStr, numPublishes, \
                                  numPings, numRetries, \
                                  numAcks, numAvgLatency)
            mqttSNStatInfoList.append(info)
    ##MAPFUNC.printDevStatusList(mqttSNStatInfoList)
    return mqttSNStatInfoList


# tested
def GetMqttBKStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'mqttbkstat' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c mqttbkstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of MQTTBKstat object if statistics of mqttbkstat devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetMqttBKStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetMqttBKStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetMqttBKStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_MQTT_BK_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    mqttBKStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetMqttBKStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_MQTT_BK_STATISTICS", \
                                                              "PACKET_MQTT_BK_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numPublishes = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numPings = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numRetries = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAcks = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAvgLatency = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = mqttSNStatInfo(deviceNameStr, numPublishes, \
                                  numPings, numRetries, \
                                  numAcks, numAvgLatency)
            mqttBKStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(mqttBKStatInfoList)
    return mqttBKStatInfoList


# tested
def GetModbusStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'modbusstat' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c modbusstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of Modbusstat object if statistics of modbusstat devices are available
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetModbusStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetModbusStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetModbusStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_MODBUS_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    modbusStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetModbusStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_MODBUS_STATISTICS", \
                                                              "PACKET_MODBUS_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numActiveConnections = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSessions = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numCommands = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = modbusStatInfo(deviceNameStr, numActiveConnections, \
                                  numSessions, numCommands)
            modbusStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(modbusStatInfoList)
    return modbusStatInfoList


# tested
def GetMqttUserStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'mqttstat' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c mqttstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of MQTTstat object if statistics of mqtt devices are available
    """

    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetMqttUserStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetMqttUserStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetMqttUserStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_MQTT_USER_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    mqttUserStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetMqttUserStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_MQTT_USER_STATISTICS", \
                                                              "PACKET_MQTT_USER_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            numStat = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            labelLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            label = struct.unpack_from("%ds" % labelLen, replyBuf, index)[0].decode()
            index += labelLen

            userStatVal = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = mqttUserStatInfo(deviceNameStr, numStat, \
                                    label, userStatVal)
            mqttUserStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(mqttUserStatInfoList)
    return mqttUserStatInfoList


def GetAllIOTStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends '' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c mqttstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of MQTTstat object if statistics of mqtt devices are available
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetAllIOTStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetAllIOTStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetAllIOTStatisticsFromMap : Could not retrieve map info{0}".format(mapName))
    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_ALL_IOT_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    allIOTStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetAllIOTStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_ALL_IOT_STATISTICS", \
                                                              "PACKET_ALL_IOT_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            coapReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            coapRespPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttPubPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttAvgLatPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttSnPubPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttSnAvgLatPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttBrPubPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            mqttBrAvgLatPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            modbusSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            modbusCommandPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            httpCLRequests = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            httpCLResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            bacnetRequests = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            bacnetResponses = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = allIOTStatInfo(deviceNameStr, coapReqPkts, coapRespPkts, \
                                  mqttPubPkts, mqttAvgLatPkts, \
                                  mqttSnPubPkts, mqttSnAvgLatPkts, \
                                  mqttBrPubPkts, mqttBrAvgLatPkts, \
                                  modbusSessionPkts, modbusCommandPkts, \
                                  httpCLRequests, httpCLResponses, \
                                  bacnetRequests, bacnetResponses \
                                  )

            allIOTStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(allIOTStatInfoList)
    return allIOTStatInfoList


def GetAllProtocolStatisticsFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'allstats' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c allstats -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of allstats object if statistics of all devices are available
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetAllProtocolStatisticsFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetAllProtocolStatisticsFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetAllProtocolStatisticsFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_ALL_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    allProtocolStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetAllProtocolStatisticsFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_ALL_STATISTICS", \
                                                              "PACKET_ALL_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numRespPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTrapPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTelnetSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTelnetCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSSHSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSSHCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTL1SessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numTL1CmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNetflowSentPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNetflowPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numActSoapSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSoapSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numSoapCommandPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numActCloudSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numCloudSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numCloudCommandPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numCoapReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numCoapRespPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMqttPublishes = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMqttAcks = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numModbuSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numModbuCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numHttpClientReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numHttpClientRespPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numBacnetReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numBacnetRespPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numActNetconfSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNetconfSessionPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numNetconfCmdPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMaxQueueLenPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMinRespTimePkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMaxRespTimePkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numStopwatchReqPkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAvgRespTimePkts = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = allProtocolStatInfo(deviceNameStr, \
                                       numReqPkts, numRespPkts, numTrapPkts, \
                                       numTelnetSessionPkts, numTelnetCmdPkts, \
                                       numSSHSessionPkts, numSSHCmdPkts, \
                                       numTL1SessionPkts, numTL1CmdPkts, \
                                       numNetflowSentPkts, numNetflowPkts, \
                                       numActSoapSessionPkts, numSoapSessionPkts, numSoapCommandPkts, \
                                       numActCloudSessionPkts, numCloudSessionPkts, numCloudCommandPkts, \
                                       numCoapReqPkts, numCoapRespPkts, \
                                       numMqttPublishes, numMqttAcks, \
                                       numModbuSessionPkts, numModbuCmdPkts, \
                                       numHttpClientReqPkts, numHttpClientRespPkts, \
                                       numBacnetReqPkts, numBacnetRespPkts, \
                                       numActNetconfSessionPkts, numNetconfSessionPkts, numNetconfCmdPkts, \
                                       numMaxQueueLenPkts, numMinRespTimePkts, numMaxRespTimePkts, \
                                       numStopwatchReqPkts, numAvgRespTimePkts
                                       )
            allProtocolStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(allProtocolStatInfoList)
    return allProtocolStatInfoList


# exported
def GetPerfStatFromMap(saproCommObj, mapName, devName=""):
    """
       Sends 'perfstat' command to get statistics of a specified map.

       Equivalent to executing: sapcnsl -p 2100 -m map1.map -c perfstat -d deviceName


       Args:

           saproCommObj:    An instance of SaproCommunication class.
           mapName:         Name of a Map, which is being stopped.
           deviceName:      Name of a telnet device whose statistics is being fetched.

       Returns:

           List of perfstat object if statistics of perfstat devices are available
    """
    if not saproCommObj:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "GetPerfStatFromMap : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if mapName == "":
        print("Map name is not specified. Please specify the map name and try again...\n")
        raise SaproException("GetPerfStatFromMap : Map name not specified")

    mapInfo = None
    mapInfo = MAPFUNC.getMapInfo(saproCommObj, mapName)
    if mapInfo is None:
        print("Error: Unable to get map port. Please check whether the map is running or not and try again...\n")
        raise SaproException("GetPerfStatFromMap : Could not retrieve map info{0}".format(mapName))

    request = saproCommObj.CreateRequestHeaderPacketForDevString(
        saproCommObj.getValue("PACKET_FROM_MAP_MGR_TO_GET_PERF_STATISTICS"), devName)
    mapSock = saproCommObj.connectToMapPort(mapInfo.hostIdByteArray, mapInfo.mapPort)
    mapSock.send(request, len(request))
    perfStatInfoList = list()

    remainingDevices = 1
    while remainingDevices > 0:
        index = 0

        replyBuf = saproCommObj.getReplyDataBufferFromMapPort(mapSock, \
                                                              "GetPerfStatFromMap", \
                                                              "PACKET_FROM_MAP_MGR_TO_GET_PERF_STATISTICS", \
                                                              "PACKET_PERF_STATISTICS_RETURNED_FROM_SERVER")

        numDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        remainingDevices = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        for i in range(numDevices):
            deviceNameStrLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")

            deviceNameStr = struct.unpack_from("%ds" % deviceNameStrLen, replyBuf, index)[0].decode()
            index += deviceNameStrLen

            numRequest = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMinResp = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMaxResp = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numAvgResp = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            numMaxQueueLength = struct.unpack_from(">l", replyBuf, index)[0]
            index += struct.calcsize(">l")

            info = perfStatInfo(deviceNameStr, numRequest, \
                                numMinResp, numMaxResp, numAvgResp, numMaxQueueLength)
            perfStatInfoList.append(info)
    # MAPFUNC.printDevStatusList(perfStatInfoList)
    return perfStatInfoList
