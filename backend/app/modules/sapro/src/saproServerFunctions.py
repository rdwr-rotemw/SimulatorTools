# -*- coding: utf-8 -*-
import struct
from backend.app.modules.sapro.src.saproException import SaproException
import backend.app.modules.sapro.src.saproMapFunctions as MAPFUNC
from backend.app.modules.sapro.src.returnTypes.VersionInfo import VersionInfo
from backend.app.modules.sapro.src.returnTypes.MapAllStatInfo import mapStatsInfo
from backend.app.modules.sapro.src.returnTypes.LicenseInfo import licenseInfo
from backend.app.modules.sapro.src.returnTypes.LicenseInfo import fullLicenseInfo


def PrintAllStat(mapStatList):
    for val in enumerate(mapStatList):
        print (val)


def SendTerminateCmdToServer(saproCommObj):
    """
        Sends 'terminate' command to stop the server.

        Equivalent to executing: sapcnsl -p 2100 -c terminate

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("SendTerminateCmdToServer : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    headerPacket = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_TERMINATE"), saproCommObj.getValue("HEADERLENGTH"))

    saproCommObj.sock.send(headerPacket,len(headerPacket))

    replyBuf = ""
    if saproCommObj.newVersion is True:
        replyBuf = saproCommObj.getReplyDataBuffer("SendTerminateCmdToServer","PACKET_NS_TERMINATE")

    if replyBuf == "":
        return "Request to terminate server sent."
    else:
        index = 0
        msgLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")
        msg = struct.unpack_from("%ds"%msgLen, replyBuf, index)[0].decode()
        return msg


def SendStopAllCmdToServer(saproCommObj):
    """
        Sends 'stopall' command to stop all running maps.

        Equivalent to executing: sapcnsl -p 2100 -c stopall -i 192.128.100.1

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            An appropriate message whether the command could be sent or not.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("SendTerminateCmdToServer : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    mapList = MAPFUNC.getMapListFromServer(saproCommObj)

    retVal = ""
    for mapInfo in mapList:
        print("$$$$$$$$$$$$",mapInfo.mapName)
        retVal = retVal + MAPFUNC.SendStopCmdToMap(saproCommObj, mapInfo.mapName)

    return retVal


def ShowVersion(saproCommObj):
    """
        Sends 'showversion' command to get the Sapro server version related information. This function returns reference of hash array that contains
        following fields :-
        product_name, major_version, minor_version, build_version, os_platform, current_date, current_time, product_flavour, device_and_ip_count.

        Equivalent to executing: sapcnsl -p 2100 -c showversion

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            An object of VersionInfo class that includes server's information'
    """
    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("ShowVersion : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    headerPacket = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GET_SAPSAENT_VERSION_INFO"), saproCommObj.getValue("HEADERLENGTH"))

    saproCommObj.sock.send(headerPacket, len(headerPacket))

    replyBuf = saproCommObj.getReplyDataBuffer("ShowVersion", "PACKET_NS_GET_SAPSAENT_VERSION_INFO")

    if replyBuf == "":
        print ("Unable to get server's version information.")
        return None

    index = 0

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    product_name = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    major_version = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    minor_version = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    build_version = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    os_platform = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    current_date = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    current_time = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    product_flavour = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    device_and_ip_count = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    verInfo = VersionInfo(product_name, major_version, minor_version, build_version, os_platform, current_date, current_time, product_flavour, device_and_ip_count)
    print(verInfo.product_name,verInfo.major_version,verInfo.minor_version)
    return verInfo


def GetAllStats(saproCommObj):
    """

        Sends 'allstats' command to the Sapro server to get all statistics such as no. of sessions, no. of commands from all running maps. This function returns
        list of hash refernces of all maps statistics. An element of a list contains name of the map and its related statistics. A hash will have following fields:-
        mapname, allinpackets, alldevresps, telnetsessions, telnetcommands, sshsessions, sshcommands, TL1sessions, TL1commands, netflowpkts, activesoapsessions,
        soapsessions, soapcommands.

        Equivalent to executing: sapcnsl -p 2100 -c allstats

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            A list of tuples, each touple consists of mapname and all above statistical information.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("GetAllStats : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    mapList = MAPFUNC.getMapListFromServer(saproCommObj)

    reqPacket = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_FROM_MGR_TO_GET_STATISTICS_FOR_MAPS"), saproCommObj.getValue("HEADERLENGTH"))

    mapStatInfoArr = list()
    for mapInfo in mapList:

        replyBuf = saproCommObj.connectToMapAndGetResponse(reqPacket, mapInfo.mapPort, True)
        index = 0

        strLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")
        mapName = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
        index += strLen

        allinpackets = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        alldevresps = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        telnetsessions = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        telnetcommands = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        sshsessions = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        sshcommands = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        TL1sessions = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        TL1commands = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        netflowpkts = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        activesoapsessions = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        soapsessions = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        soapcommands = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        netflowpktcount = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        netflowflow = struct.unpack_from(">l", replyBuf, index)[0]
        index += struct.calcsize(">l")

        mapStatInfo = mapStatsInfo(mapName, allinpackets, alldevresps, telnetsessions, telnetcommands, sshsessions, sshcommands, TL1sessions, TL1commands, netflowpkts, activesoapsessions, soapsessions, soapcommands, netflowpktcount, netflowflow)

        mapStatInfoArr.append(mapStatInfo)
        PrintAllStat(mapStatInfo)

    return mapStatInfoArr


#exported
def SendTriggerFlagAction(saproCommObj, flagVal, mapName="", devName=""):
    """
        Sets the flagVal value to all running maps if mapName is not specified.
                             OR
        Sets the flagVal value to all running devices of a specified map.
                             OR
        Sets the flagVal value to specified device of a specified map.

        Args:

            saproCommObj: An instance of SaproCommunication class.
            mapName     : Name of the map to whome the flag is set.
                          This is an optional parameter.
            deviceName  : Name of the device to whome flag will be set.
                          This is an optional parameter.

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("SendTriggerFlagAction : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if flagVal is None or flagVal == "":
        print("Please specify flag value and try again...\n")
        raise SaproException("Please specify flag value and try again...")

    mapList = []

    if mapName == "":
        mapList = MAPFUNC.getMapListFromServer(saproCommObj)
    else:
        mapInfo = MAPFUNC.getMapInfo(saproCommObj,mapName)
        mapList.append(mapInfo)

    if len(mapList) <= 0:
        print("There is no running map")
        return False

    msg = ""
    for mapInfo in mapList:
        reqPacket = saproCommObj.CreateFlagActionRequestPacket(saproCommObj.getValue("PACKET_ASK_SERVER_TO_SET_FLAG_ACTION"), flagVal, devName)

        replyBuf = saproCommObj.connectToMapAndGetResponse(reqPacket, mapInfo.mapPort, True, "PACKET_PROCESSING_OK_IN_CLIENT")
        index = 0

        strLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        msg += struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
        index += strLen

    print("Request sent to all running maps")
    return True


#exported
def GetLogfileName(saproCommObj):
    """
        This is to get log file name from sapns server.

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            Name of the log file.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("GetLogfileName : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    reqBuf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GET_LOGFILENAME"),saproCommObj.getValue("HEADERLENGTH"))

    saproCommObj.sock.send(reqBuf,len(reqBuf))

    replyBuf = ""
    replyBuf = saproCommObj.getReplyDataBuffer("GetLogfileName","PACKET_NS_GET_LOGFILENAME","PACKET_NS_REPLY_GET_LOGFILENAME")

    if replyBuf == "":
        raise SaproException("Get Log File: Unable to receive data from socket.")

    index = 0
    strLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = struct.unpack_from("%ds"%strLen, replyBuf, index)[0].decode()
    index += strLen

    return msg


def GetTempFileName(saproCommObj,fileName):

    """
        This to get temparory file name from sapns server.

        Args:

            saproCommObj: An instance of SaproCommunication class.
            fileName - Name of the temp file  to be created at sapns server. It can be empty string

        Returns:

            Returns the name of the temporary file returned by sapns server.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("GetTempFileName : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    reqBuf = saproCommObj.CreateRequestHeaderPacketForGetTempFile(saproCommObj.getValue("PACKET_NS_FILE_OPER"),6,fileName)

    saproCommObj.sock.send(reqBuf,len(reqBuf))

    replyBuf = ""
    replyBuf = saproCommObj.getReplyDataBuffer("GetTempFileName","PACKET_NS_FILE_OPER","PACKET_NS_REPLY_FILE_OPER")

    if replyBuf == "":
        raise SaproException("Get temp file name: Unable to receive data from socket.")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds"%fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    if status != saproCommObj.getFileOperStatus("FILE_OPER_OK") and status != saproCommObj.getFileOperStatus("FILE_OPER_ERROR") and status != saproCommObj.getFileOperStatus("FILE_OPER_DONE"):
        raise SaproException("An unexpected File status has been received from server")

    if status == saproCommObj.getFileOperStatus("FILE_OPER_OK"):
        numBytes = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")
        retVal = struct.unpack_from("%ds"%numBytes, replyBuf, index)[0].decode()
        index += numBytes
        print(retVal)

    return fileName

#exported
def GetLicenseInfo(saproCommObj):
    """
        This is to get brief licence information from sapns server.

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            A licenceInfo tuple.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("GetLicenseInfo : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    reqBuf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GETLICENSE_INFO"),saproCommObj.getValue("HEADERLENGTH"))

    saproCommObj.sock.send(reqBuf,len(reqBuf))

    replyBuf = ""
    replyBuf = saproCommObj.getReplyDataBuffer("GetLicenseInfo","PACKET_NS_GETLICENSE_INFO","")

    if replyBuf == "":
        raise SaproException("GetLicenceInfo: Unable to receive data from socket.")

    index = 0

    maxDevCnt = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    currDevCnt = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    licType = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    errCode = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    return licenseInfo(maxDevCnt, currDevCnt, licType, errCode)


#exported
def GetFullLicenseInfo(saproCommObj):
    """
        This is to get detailed licence information from sapns server.

        Args:

            saproCommObj: An instance of SaproCommunication class.

        Returns:

            A fullLcenceInfo tuple.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("GetFullLicenseInfo : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    reqBuf = saproCommObj.createRequestHeaderPacket(saproCommObj.getValue("PACKET_NS_GETFULLLIC_INFO"), saproCommObj.getValue("HEADERLENGTH"))

    saproCommObj.sock.send(reqBuf, len(reqBuf))

    replyBuf = ""
    replyBuf = saproCommObj.getReplyDataBuffer("GetFullLicenseInfo", "PACKET_NS_GETFULLLIC_INFO", "")

    if replyBuf == "":
        raise SaproException("GetFullLicenseInfo: Unable to receive data from socket.")

    index = 0

    maxDevCnt = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    currDevCnt = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    licType = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    expDtTimestamp = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")
    expDate = "%04d-%02d-%02d" % ((expDtTimestamp / 10000), ((expDtTimestamp % 10000) / 100), ((expDtTimestamp % 10000) % 100))

    regId = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    numBytes = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    hostId = struct.unpack_from("%ds"%numBytes, replyBuf, index)[0].decode()
    index += numBytes

    modMask = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    errCode = struct.unpack_from(">l", replyBuf, index)[0]
    index += struct.calcsize(">l")

    numBytes = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    serverIp = struct.unpack_from("%ds"%numBytes, replyBuf, index)[0].decode()
    index += numBytes

    numBytes = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")
    serverPort = struct.unpack_from("%ds"%numBytes, replyBuf, index)[0].decode()
    index += numBytes

    return fullLicenseInfo(maxDevCnt, currDevCnt, licType, expDate, regId,
                           hostId, modMask, errCode, serverIp, serverPort)
