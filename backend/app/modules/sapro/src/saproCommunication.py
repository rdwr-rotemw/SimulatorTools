import struct

from backend.app.modules.sapro.src import saproConstants
from backend.app.modules.sapro.src.saproException import SaproException
from backend.app.modules.sapro.src.saproSocket import SaproSocket


class SaproCommunication:
    """
        This class holds the connected information between server and the
        application.
    """

    def __init__(self):
        """
            Constructs SaproCommunication class's object.
        """

        self.serverIP = None
        self.serverPort = None
        self.sock = SaproSocket()
        # self.oldVersion = 0
        self.newVersion = True
        self.debug = 0
        self.constantObj = saproConstants.ConstantsMap()
        self.stopMapDelay = self.constantObj.getConstant("DEF_STOPMAPDELAY")

    def getValue(self, key):
        return (self.constantObj.getConstant(key))

    def getValueStr(self, key):
        return (self.constantObj.getConstantStr(key))

    def getFileOperStatus(self, key):
        return (self.constantObj.getFileOperStatus(key))

    def getDirOperStatus(self, key):
        return (self.constantObj.getDirOperStatus(key))

    def closeConnection(self):
        """
            This will end the connection between server and application.
        """

        self.sock.close()

    def initConnection(self, serverIP1, serverPort1):

        """
            This function must be called as soon as the object of
            SaproCommunication class is created.

            This function initiates communication between server and
            calling application.
        """

        try:
            self.serverIP = serverIP1  # ipaddress.ip_address(serverIP1)
            self.serverPort = serverPort1
            print("InitConnection: IPAddress:%s" % self.serverIP)
            # self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # self.sock.connect((serverIP1,serverPort1))
            self.sock.connect(serverIP1, serverPort1)

        except OSError as err:
            raise SaproException(format(err))
        except ValueError as err:
            # print("IPAddress is not in the proper format",format(err))
            raise SaproException(format(err))

    def setNewVersion(self, isNewVersion):

        """
            This by default is set to True. This is to make application compatible
            with old versioned server. If 'isNewVersion' is False, it supports
            old versioned server and 'True' value supports current servers.
        """

        self.newVersion = isNewVersion

    def SetStopMapDelay(self, delay):
        if isinstance(delay, int) == True:
            if delay <= 0:
                raise SaproException("SetStopMapDelay: delay can not be <= 0")
            else:
                self.stopMapDelay = delay
        else:
            print("Wrong value of Map stop delay. Continuing with default delay as 10 seconds")

    def SetDebugOn(self, debug):

        """
            'debug' =  1, will turn ON debugging.
            'debug' =  0, will turn OFF debugging.
        """

        if debug != 0 and debug != 1:
            raise SaproException("SetDebugOn: Please specify 0 OR 1. 0 to set debug off, 1 to set debug on.")
        self.debug = 0
        if (debug == 1):
            self.debug = 1

    def CreateRequesttHeaderPacketForStartMapCommand(self, msgType, mapName, logFileName, startListFile="none"):
        mapNameLen = len(mapName)

        configFile = "./../bin/config.inp"
        configFileLen = len(configFile)

        startListFileLen = len(startListFile)

        udpPort = "161"
        udpPortLen = len(udpPort)

        mapMgr = "0"
        mapMgrLen = len(mapMgr)

        procId = "0"
        procIdLen = len(procId)

        ifce = self.sock.sock.getpeername()[0]
        ifceLen = len(ifce)

        if (logFileName is None) or (logFileName == ""):
            logFileName = mapName
            if logFileName.find("/") >= 0:
                logFileName = logFileName.split("/")[-1]

            if logFileName.find(".") >= 0:
                logFileName = (logFileName.split(".")[0]) + ".log"

        logFileNameLen = len(logFileName)

        shorttLen = self.getValue("SHORT_LENGTH")
        totalLength = self.getValue("HEADERLENGTH") + shorttLen + configFileLen
        totalLength += shorttLen + mapNameLen + shorttLen + startListFileLen
        totalLength += shorttLen + ifceLen
        totalLength += shorttLen + udpPortLen
        totalLength += shorttLen + logFileNameLen + shorttLen + mapMgrLen
        totalLength += shorttLen + procIdLen

        reqBuf = bytearray(totalLength)
        index = 0
        struct.pack_into(">l", reqBuf, index, totalLength)
        index += self.getValue("INT_LENGTH")
        struct.pack_into(">l", reqBuf, index, self.getValue(msgType))
        index += self.getValue("INT_LENGTH")

        index = self.getValue("HEADERLENGTH")
        struct.pack_into(">h", reqBuf, index, configFileLen)
        index += shorttLen
        struct.pack_into("%ds" % configFileLen, reqBuf, index, configFile.encode())
        index += configFileLen

        struct.pack_into(">h", reqBuf, index, mapNameLen)
        index += shorttLen
        struct.pack_into("%ds" % mapNameLen, reqBuf, index, mapName.encode())
        index += mapNameLen

        struct.pack_into(">h", reqBuf, index, startListFileLen)
        index += shorttLen
        struct.pack_into("%ds" % startListFileLen, reqBuf, index, startListFile.encode())
        index += startListFileLen

        struct.pack_into(">h", reqBuf, index, ifceLen)
        index += shorttLen
        struct.pack_into("%ds" % ifceLen, reqBuf, index, ifce.encode())
        index += ifceLen

        struct.pack_into(">h", reqBuf, index, udpPortLen)
        index += shorttLen
        struct.pack_into("%ds" % udpPortLen, reqBuf, index, udpPort.encode())
        index += udpPortLen

        struct.pack_into(">h", reqBuf, index, logFileNameLen)
        index += shorttLen
        struct.pack_into("%ds" % logFileNameLen, reqBuf, index, logFileName.encode())
        index += logFileNameLen

        struct.pack_into(">h", reqBuf, index, mapMgrLen)
        index += shorttLen
        struct.pack_into("%ds" % mapMgrLen, reqBuf, index, mapMgr.encode())
        index += mapMgrLen

        struct.pack_into(">h", reqBuf, index, procIdLen)
        index += shorttLen
        struct.pack_into("%ds" % procIdLen, reqBuf, index, procId.encode())
        index += procIdLen

        return reqBuf

    def CreateRequestHeaderPacketForDevString(self, msgType, devName):
        index = 0
        if devName == "" or devName == None:
            devNameLen = 0
        else:
            devNameLen = len(devName)
        totalLength = self.getValue("HEADERLENGTH") + self.getValue("SHORT_LENGTH") + devNameLen
        headerBuffer = bytearray(totalLength)
        # headerBuffer[index] = struct.pack(">l",packetLength)
        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print(headerBuffer)
        # print("Length:",len(headerBuffer))
        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, devNameLen)
        index += struct.calcsize(">h")
        if devNameLen != 0:
            struct.pack_into("%ds" % devNameLen, headerBuffer, index, devName.encode())
        return (headerBuffer)

    def SendScenarioFile(self, mapServer, mapPort, scenarioFile, deviceName, args):
        requestPac = self.CreateRequestHeaderPacketForScenarioFile(self.getValue("PACKET_ASK_SERVER_TO_RUN_SCENARIO"), \
                                                                   scenarioFile, \
                                                                   deviceName, args)

        if (self.newVersion == True):
            recvBuf = self.connectToMapAndGetResponse(requestPac, mapPort, True, "PACKET_ASK_SERVER_TO_RUN_SCENARIO")
            msgLen = struct.unpack_from(">h", recvBuf, 0)[0]
            msg = struct.unpack_from("%ds" % msgLen, recvBuf, struct.calcsize(">h"))[0]
            return (msg)
        else:
            self.connectToMapAndGetResponse(requestPac, mapPort, False, "PACKET_ASK_SERVER_TO_RUN_SCENARIO")
            return ("Request to send scenario file to map sent.")

    def createRequestHeaderPacket(self, msgType, packetLength):
        index = 0
        headerBuffer = bytearray(self.getValue("HEADERLENGTH"))
        # headerBuffer[index] = struct.pack(">l",packetLength)
        struct.pack_into(">l", headerBuffer, index, packetLength)
        index += self.getValue("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.getValue("INT_LENGTH")
        # print(headerBuffer)
        # print("Length:",len(headerBuffer))

        """
        aa = bytearray(10)
        aa = struct.unpack(">l",headerBuffer)
        aa = struct.unpack_from(">l",headerBuffer,0)
        print("aa",aa)
        """
        return (headerBuffer)

    def getReplyDataBuffer(self, functionName, msgType, replyStatusToCheck=""):
        buf = bytearray()
        buf = self.sock.recv(self.getValue("INT_LENGTH"))
        if buf == "":
            print("getReplyDataBuffer : Unable to receive data from socket.\n")
            raise SaproException(
                "getReplyDataBuffer - Error for {0}-{1} : Unable to receive data from socket".format(functionName,
                                                                                                     msgType))
        len1 = struct.unpack_from(">l", buf, 0)[0]
        # print("Total buffer length received:",len1[0])
        buf = bytearray()
        # print("Before : Recv Buffer Len",len(buf))
        buf = self.sock.recv(len1 - self.getValue("INT_LENGTH"))
        if buf == "":
            print("getReplyDataBuffer - Unable to receive data from socket.\n")
            raise SaproException(
                "getReplyDataBuffer - Error for function {0}-{1} : Unable to receive data from socket.".format(
                    functionName, msgType))
        # print("Recv Buffer Len",len(buf))
        # print(buf)
        replyStatus = struct.unpack_from(">l", buf, 0)[0]
        receivedData = buf[76:]

        if (replyStatusToCheck != ""):
            if (self.getValue(replyStatusToCheck) == replyStatus):
                return receivedData
            else:
                raise SaproException(
                    "Reply Error:For function {0}-{1} Expexted Status{2} , Received Status:{3}".format(functionName,
                                                                                                       msgType,
                                                                                                       replyStatusToCheck,
                                                                                                       replyStatus))

        elif (replyStatus == self.getValue("PACKET_NS_REPLY_ERROR")) or (
                replyStatus == self.getValue("PACKET_NS_REPLY_ERROR_FOR_MAPVIEWER")):
            raise SaproException(
                "Reply Error:For function {0}-{1} Error Number:{2}: {3}".format(functionName, msgType, replyStatus,
                                                                                receivedData.decode()))

        return receivedData

    def getReplyDataBufferFromMapPort(self, mapSock, functionName, msgType, replyStatusToCheck=""):
        buf = bytearray()
        buf = mapSock.recv(self.getValue("INT_LENGTH"))
        if buf == "":
            print("getReplyDataBufferFromMapPort : Unable to receive data from socket.\n")
            raise SaproException(
                "getReplyDataBufferFromMapPort - Error for function {0}-{1} : Unable to receive data from socket".format(
                    functionName, msgType))
        len1 = struct.unpack_from(">l", buf, 0)[0]
        # print("Total buffer length received:",len1[0])
        buf = bytearray()
        # print("Before : Recv Buffer Len",len(buf))
        buf = mapSock.recv(len1 - self.getValue("INT_LENGTH"))
        if buf == "":
            print("getReplyDataBufferFromMapPort - Unable to receive data from socket.\n")
            raise SaproException(
                "getReplyDataBufferFromMapPort - Error for function {0}-{1} : Unable to receive data from socket.".format(
                    functionName, msgType))

        replyStatus = struct.unpack_from(">l", buf, 0)[0]
        receivedData = buf[76:]

        if (replyStatusToCheck != ""):
            if (self.getValue(replyStatusToCheck) == replyStatus):
                return receivedData
            else:
                raise SaproException(
                    "getReplyDataBufferFromMapPort - Reply Error:For function {0}-{1} Expexted Status{2} , Received Status:{3},{4}".format(
                        functionName, msgType, replyStatusToCheck, replyStatus, receivedData.decode()))

        elif (replyStatus == self.getValue("PACKET_NS_REPLY_ERROR")) or (
                replyStatus == self.getValue("PACKET_NS_REPLY_ERROR_FOR_MAPVIEWER")):
            raise SaproException(
                "getReplyDataBufferFromMapPort - Reply Error:For function {0}-{1} Error Number:{2}: {3}".format(
                    functionName, msgType, replyStatus, receivedData.decode()))

        return (receivedData)

    def connectToMapAndGetResponse(self, reqPacket, mapPort, isReceiveResponse, responseCommandStr=""):
        mapsock = self.connectToMapPort(self.serverIP, mapPort)
        mapsock.send(reqPacket, len(reqPacket))

        if isReceiveResponse is False:
            mapsock.close()
            return ""

        recvBuf = ""
        recvBuf = self.getReplyDataBufferFromMapPort(mapsock, "connectToMapAndGetResponse", "", responseCommandStr)

        mapsock.close()
        return (recvBuf)

    def connectToMapPort(self, serverIP, mapPort):
        mapsock = SaproSocket()
        mapsock.connect(serverIP, mapPort)
        return (mapsock)

    def CreateRequestHeaderPacketForCommand(self, msgType, devName, cmd, cmdargs=""):
        index = 0
        if devName == "" or devName == None:
            devNameLen = 0
        else:
            devNameLen = len(devName)

        cmdLen = len(cmd)
        totalLength = 0
        if cmdargs != "":
            cmdArgLen = len(cmdargs)
            totalLength = self.getValue("HEADERLENGTH") + self.getValue("SHORT_LENGTH") + devNameLen + self.getValue(
                "SHORT_LENGTH") + cmdLen + self.getValue("SHORT_LENGTH") + cmdArgLen
        else:
            totalLength = self.getValue("HEADERLENGTH") + self.getValue("SHORT_LENGTH") + devNameLen + self.getValue(
                "SHORT_LENGTH") + cmdLen

        headerBuffer = bytearray(totalLength)
        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))
        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, devNameLen)
        index += struct.calcsize(">h")
        if devNameLen != 0:
            struct.pack_into("%ds" % devNameLen, headerBuffer, index, devName.encode())

        index += devNameLen

        struct.pack_into(">h", headerBuffer, index, cmdLen)
        index += struct.calcsize(">h")
        struct.pack_into("%ds" % cmdLen, headerBuffer, index, cmd.encode())
        index += cmdLen

        if cmdargs != "":
            struct.pack_into(">h", headerBuffer, index, cmdArgLen)
            index += struct.calcsize(">h")
            struct.pack_into("%ds" % cmdArgLen, headerBuffer, index, cmdargs.encode())
            index += cmdArgLen

        return (headerBuffer)

    def CreateRequestHeaderPacketForScenarioFile(self, msgType, fileName, devName, args=""):
        index = 0
        if devName == "" or devName == None:
            devName = "*"

        devNameLen = len(devName)

        fileNameLen = len(fileName)

        totalLength = 0
        argLen = 0
        #    newArg =  " ".join(list(map(lambda var:"\""+var+"\"" ,args.split(","))))
        if args != "":
            newArgs = ' '.join('"{}"'.format(word) for word in args.split(','))
            argLen = len(newArgs)
            args = newArgs

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      devNameLen + self.getValue("SHORT_LENGTH") + \
                      fileNameLen + self.getValue("SHORT_LENGTH") + argLen

        headerBuffer = bytearray(totalLength)
        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))
        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, fileNameLen)
        index += struct.calcsize(">h")
        struct.pack_into("%ds" % fileNameLen, headerBuffer, index, fileName.encode())
        index += fileNameLen

        struct.pack_into(">h", headerBuffer, index, devNameLen)
        index += struct.calcsize(">h")
        if devNameLen != 0:
            struct.pack_into("%ds" % devNameLen, headerBuffer, index, devName.encode())

        index += devNameLen

        struct.pack_into(">h", headerBuffer, index, argLen)
        index += struct.calcsize(">h")

        if args != "":
            struct.pack_into("%ds" % argLen, headerBuffer, index, args.encode())

        return (headerBuffer)

    def CreateRequestHeaderPacketForFileOperForRead(self, msgType, fileOperFlag, fileName, startOffset, numBytes):
        """
        """
        index = 0

        fileNameLen = len(fileName)

        totalLength = 0

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      self.getValue("SHORT_LENGTH") + fileNameLen + \
                      self.getValue("INT_LENGTH") + self.getValue("SHORT_LENGTH")

        headerBuffer = bytearray(totalLength)
        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))
        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, fileOperFlag)
        index += struct.calcsize(">h")

        struct.pack_into(">h", headerBuffer, index, fileNameLen)
        index += struct.calcsize(">h")
        struct.pack_into("%ds" % fileNameLen, headerBuffer, index, fileName.encode())
        index += fileNameLen

        struct.pack_into(">l", headerBuffer, index, startOffset)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">h", headerBuffer, index, numBytes)
        index += struct.calcsize(">h")

        return (headerBuffer)

    def CreateRequestHeaderPacketForFileOperForWrite(self, msgType, fileOperFlag, fileName, fileData, fileDataLen,
                                                     lFileOffset):
        """
        """
        index = 0
        fileNameLen = len(fileName)

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      self.getValue("SHORT_LENGTH") + fileNameLen + \
                      self.getValue("INT_LENGTH") + self.getValue("SHORT_LENGTH") + \
                      fileDataLen

        headerBuffer = bytearray(totalLength)

        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))

        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, fileOperFlag)
        index += struct.calcsize(">h")

        struct.pack_into(">h", headerBuffer, index, fileNameLen)
        index += struct.calcsize(">h")
        struct.pack_into("%ds" % fileNameLen, headerBuffer, index, fileName.encode())
        index += fileNameLen

        struct.pack_into(">l", headerBuffer, index, lFileOffset)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">h", headerBuffer, index, fileDataLen)
        index += struct.calcsize(">h")

        if self.IsByteObject(fileData) is True:
            struct.pack_into("%ds" % fileDataLen, headerBuffer, index, fileData)
        else:
            struct.pack_into("%ds" % fileDataLen, headerBuffer, index, fileData.encode())
        index += fileDataLen

        return (headerBuffer)

    def CreateRequestHeaderPacketForDirOper(self, msgType, dirOperFlg, dirName, dirFilter):
        """
        """

        index = 0
        dirNameLen = len(dirName)

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      self.getValue("SHORT_LENGTH") + dirNameLen + \
                      self.getValue("SHORT_LENGTH")

        headerBuffer = bytearray(totalLength)

        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))

        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, dirOperFlg)
        index += struct.calcsize(">h")

        struct.pack_into(">h", headerBuffer, index, dirNameLen)
        index += struct.calcsize(">h")

        struct.pack_into("%ds" % dirNameLen, headerBuffer, index, dirName.encode())
        index += dirNameLen

        filterLen = len(dirFilter)
        struct.pack_into(">h", headerBuffer, index, filterLen)
        index += struct.calcsize(">h")

        if filterLen > 0:
            struct.pack_into("%ds" % filterLen, headerBuffer, index, dirFilter.encode())
            index += filterLen

        return headerBuffer

    def CreateFlagActionRequestPacket(self, msgType, flagVal, devName=""):
        """
        """
        index = 0
        devNameLen = len(devName)

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      devNameLen + self.getValue("INT_LENGTH")

        headerBuffer = bytearray(totalLength)

        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))

        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, devNameLen)
        index += struct.calcsize(">h")

        if devNameLen > 0:
            struct.pack_into("%ds" % devNameLen, headerBuffer, index, devName.encode())
            index += devNameLen

        struct.pack_into(">l", headerBuffer, index, flagVal)
        index += self.constantObj.getConstant("INT_LENGTH")

        return headerBuffer

    def CreateRequestHeaderPacketForGetTempFile(self, msgType, fileOperFlag, fileName):
        """
        """
        lFileOffset = 0
        fileDataLen = 0

        index = 0
        fileNameLen = len(fileName)

        totalLength = self.getValue("HEADERLENGTH") + \
                      self.getValue("SHORT_LENGTH") + \
                      self.getValue("SHORT_LENGTH") + fileNameLen + \
                      self.getValue("INT_LENGTH") + self.getValue("SHORT_LENGTH")

        headerBuffer = bytearray(totalLength)

        struct.pack_into(">l", headerBuffer, index, totalLength)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">l", headerBuffer, index, msgType)
        index += self.constantObj.getConstant("INT_LENGTH")
        # print("Length:", len(headerBuffer))

        index = self.getValue("HEADERLENGTH")

        struct.pack_into(">h", headerBuffer, index, fileOperFlag)
        index += struct.calcsize(">h")

        struct.pack_into(">h", headerBuffer, index, fileNameLen)
        index += struct.calcsize(">h")
        struct.pack_into("%ds" % fileNameLen, headerBuffer, index, fileName.encode())
        index += fileNameLen

        struct.pack_into(">l", headerBuffer, index, lFileOffset)
        index += self.constantObj.getConstant("INT_LENGTH")

        struct.pack_into(">h", headerBuffer, index, fileDataLen)
        index += struct.calcsize(">h")

        return (headerBuffer)

    def IsByteObject(self, data):
        try:
            data = data.decode()
            return True
        except AttributeError:
            return False
