# -*- coding: utf-8 -*-
import struct
from backend.app.modules.sapro.src.saproException import SaproException


#exported
def CreateDirectory(saproCommObj, remoteDirName):
    """
        The directory specified as remoteDirName will be created at sapns server.

        Args:

            saproCommObj : An instance of SaproCommunication class.
            remoteDirName: Name of the directory to be created.

        Returns:

            True on Success, False on Failure.
    """
    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("CreateDirectory : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteDirName == ""):
        print ("Remote directory name can not be empty. Please specify remote directory name.\n")
        raise SaproException("Remote directory name can not be empty. Please specify remote directory name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForDirOper(saproCommObj.getValue("PACKET_NS_DIR_OPER"), 1, remoteDirName, "");
    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("CreateDirectory", "PACKET_NS_DIR_OPER", "PACKET_NS_REPLY_DIR_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds"%fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = struct.unpack_from("%ds"%msgLen, replyBuf, index)[0].decode()
    index += msgLen

    if status != saproCommObj.getDirOperStatus("DIR_OPER_OK"):
        print(msg)
        return False

    return True


#exported
def DeleteDirectory(saproCommObj, remoteDirName):
    """
        The directory specified as remoteDirName will be deleted at sapns server.

        Args:

            saproCommObj : An instance of SaproCommunication class.
            remoteDirName: Name of the directory to be deleted.

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("DeleteDirectory : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteDirName == ""):
        print ("Remote directory name can not be empty. Please specify remote directory name.\n")
        raise SaproException("Remote directory name can not be empty. Please specify remote directory name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForDirOper(saproCommObj.getValue("PACKET_NS_DIR_OPER"), 2, remoteDirName, "");
    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("DeleteDirectory", "PACKET_NS_DIR_OPER", "PACKET_NS_REPLY_DIR_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds"%fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = struct.unpack_from("%ds"%msgLen, replyBuf, index)[0].decode()
    index += msgLen

    if status != saproCommObj.getDirOperStatus("DIR_OPER_OK"):
        print(msg)
        return False

    return True


#exported
def DirectoryExists(saproCommObj, remoteDirName):
    """
        The directory specified as remoteDirName will be searched at sapns server
        and returns appropriate result.

        Args:

            saproCommObj : An instance of SaproCommunication class.
            remoteDirName: Name of the directory to be searched.

        Returns:

            True on Success, False on Failure.
    """
    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("DirectoryExists : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteDirName == ""):
        print ("Remote directory name can not be empty. Please specify remote directory name.\n")
        raise SaproException("Remote directory name can not be empty. Please specify remote directory name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForDirOper(saproCommObj.getValue("PACKET_NS_DIR_OPER"), 3, remoteDirName, "");
    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("DirectoryExists", "PACKET_NS_DIR_OPER", "PACKET_NS_REPLY_DIR_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds"%fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = struct.unpack_from("%ds"%msgLen, replyBuf, index)[0].decode()
    index += msgLen

    if status != saproCommObj.getDirOperStatus("DIR_OPER_OK"):
        print(msg)
        return False

    return True


#exported
def DirList(saproCommObj, remoteDirName, dirFilter=""):
    """
        This to get list of files present in the directory
        specified as $remoteDirName at sapns server.

        Args:

            saproCommObj : An instance of SaproCommunication class.
            remoteDirName: Name of the directory to be searched.
            dirFilter    : specify filter here as a string

        Returns:

            List of files present in specified directory.
    """
    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException("DirList : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteDirName == ""):
        print ("Remote directory name can not be empty. Please specify remote directory name.\n")
        raise SaproException("Remote directory name can not be empty. Please specify remote directory name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForDirOper(saproCommObj.getValue("PACKET_NS_DIR_OPER"), 4, remoteDirName, dirFilter);
    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("DirList", "PACKET_NS_DIR_OPER", "PACKET_NS_REPLY_DIR_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds"%fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    numFiles = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNames = list()

    if status != saproCommObj.getDirOperStatus("DIR_OPER_OK"):
        msg = struct.unpack_from("%ds"%numFiles, replyBuf, index)[0].decode()
        index += numFiles
        fileNames.append(msg)
        return fileNames

    if status == saproCommObj.getDirOperStatus("DIR_OPER_OK") and numFiles > 0:
        while numFiles > 0:
            numBytes = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")
            dirFile = struct.unpack_from("%ds"%numBytes, replyBuf, index)[0].decode()
            index += numBytes
            fileNames.append(dirFile)
            numFiles -= 1

    return fileNames