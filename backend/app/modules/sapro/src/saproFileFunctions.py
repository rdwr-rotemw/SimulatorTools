# -*- coding: utf-8 -*-
import os
import struct

# exported
from backend.app.modules.sapro.src.saproException import SaproException


def DeleteFile(saproCommObj, remoteFileName):
    """
        Sends the name of the file, which is to be deleted from sapns server.

        Args:

            saproCommObj : An instance of SaproCommunication class.
            remoteDirName: Name of the file from sapns server to be deleted.

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "DeleteFile : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteFileName == ""):
        print("Remote file name can not be empty. Please specify remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForFileOperForRead(
        saproCommObj.getValue("PACKET_NS_FILE_OPER"), 3, remoteFileName, 0, 0)

    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("ReadFile", "PACKET_NS_FILE_OPER", "PACKET_NS_REPLY_FILE_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds" % fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    msgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()
    index += msgLen

    if status != saproCommObj.getFileOperStatus("FILE_OPER_OK"):
        print(msg)
        return False

    return True


# exported
def ReadFile(saproCommObj, remoteFileName, localFileName):
    """
        Reads the contnets of the remoteFileName into localFileName.

        Args:

            saproCommObj  : An instance of SaproCommunication class.
            remoteFileName: Name of the file from sapns server, which to be read.
            localFileName : Name of the local file to be created to save above file's data.

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "ReadFile : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteFileName == ""):
        print("Remote file name can not be empty. Please specify remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    if (localFileName == ""):
        print("Local file name can not be empty. Please specify local file name.\n")
        raise SaproException("Local file name can not be empty. Please specify local file name.")

    lFile = None
    try:
        lFile = open(localFileName, 'wb')
    except IOError as err:
        raise SaproException(format(err))

    fileOffset = 0
    status = saproCommObj.getFileOperStatus("FILE_OPER_OK")

    while status == saproCommObj.getFileOperStatus("FILE_OPER_OK"):
        requestBuffer = saproCommObj.CreateRequestHeaderPacketForFileOperForRead(
            saproCommObj.getValue("PACKET_NS_FILE_OPER"), 1, remoteFileName, fileOffset, 0)

        saproCommObj.sock.send(requestBuffer, len(requestBuffer))

        replyBuf = saproCommObj.getReplyDataBuffer("ReadFile", "PACKET_NS_FILE_OPER", "PACKET_NS_REPLY_FILE_OPER")

        index = 0

        status = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileName = struct.unpack_from("%ds" % fileNameLen, replyBuf, index)[0].decode()
        index += fileNameLen

        if status != saproCommObj.getFileOperStatus("FILE_OPER_OK") and status != saproCommObj.getFileOperStatus(
                "FILE_OPER_ERROR") and status != saproCommObj.getFileOperStatus("FILE_OPER_DONE"):
            lFile.close()
            raise SaproException("An unexpected File status has been received from server")

        if status == saproCommObj.getFileOperStatus("FILE_OPER_ERROR"):
            msgLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")
            msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()
            index += fileNameLen
            lFile.close()
            raise SaproException(msg)

        contentLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")
        fileOffset += contentLen
        if contentLen > 0:
            contents = struct.unpack_from("%ds" % contentLen, replyBuf, index)[0].decode()
            index += contentLen
            if status == saproCommObj.getFileOperStatus("FILE_OPER_OK"):
                lFile.write(bytes(contents, 'UTF-8'))

    lFile.close()
    if status == saproCommObj.getFileOperStatus("FILE_OPER_DONE"):
        return True
    else:
        return False


# exported
def ReadFileIntoString(saproCommObj, remoteFileName):
    """
        Reads the contnets of the remoteFileName into a string.

        Args:

            saproCommObj  : An instance of SaproCommunication class.
            remoteFileName: Name of the file from sapns server, which to be read.

        Returns:

            Returns file's data.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "ReadFileIntoString : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteFileName == ""):
        print("Remote file name can not be empty. Please specify remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    fileOffset = 0
    status = saproCommObj.getFileOperStatus("FILE_OPER_OK")
    fileContents = ""
    while status == saproCommObj.getFileOperStatus("FILE_OPER_OK"):
        requestBuffer = saproCommObj.CreateRequestHeaderPacketForFileOperForRead(
            saproCommObj.getValue("PACKET_NS_FILE_OPER"), 1, remoteFileName, fileOffset, 0)

        saproCommObj.sock.send(requestBuffer, len(requestBuffer))

        replyBuf = saproCommObj.getReplyDataBuffer("ReadFile", "PACKET_NS_FILE_OPER", "PACKET_NS_REPLY_FILE_OPER")

        index = 0

        status = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileName = struct.unpack_from("%ds" % fileNameLen, replyBuf, index)[0].decode()
        index += fileNameLen

        if status != saproCommObj.getFileOperStatus("FILE_OPER_OK") and status != saproCommObj.getFileOperStatus(
                "FILE_OPER_ERROR") and status != saproCommObj.getFileOperStatus("FILE_OPER_DONE"):
            raise SaproException("An unexpected File status has been received from server")

        if status == saproCommObj.getFileOperStatus("FILE_OPER_ERROR"):
            msgLen = struct.unpack_from(">h", replyBuf, index)[0]
            index += struct.calcsize(">h")
            msg = struct.unpack_from("%ds" % msgLen, replyBuf, index)[0].decode()
            index += fileNameLen
            raise SaproException(msg)

        contentLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")
        fileOffset += contentLen
        if contentLen > 0:
            contents = struct.unpack_from("%ds" % contentLen, replyBuf, index)[0].decode()
            index += contentLen
            if status == saproCommObj.getFileOperStatus("FILE_OPER_OK"):
                fileContents += contents

    if status == saproCommObj.getFileOperStatus("FILE_OPER_DONE"):
        return fileContents
    else:
        return ""


# exported
def RenameFile(saproCommObj, oldRemoteFileName, newRemoteFileName):
    """
        Renames the file specified by $oldRemoteFileName with file name
        specified by $newRemoteFileName at sapns server.

        Args:

            saproCommObj     : An instance of SaproCommunication class.
            oldRemoteFileName: Name of the file to be renamed.
            newRemoteFileName: New name of the above file.

        Returns:

            True on Success, False on Failure.
    """
    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "RenameFile : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (oldRemoteFileName == ""):
        print("Old remote file name can not be empty. Please specify old remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    if (newRemoteFileName == ""):
        print("New remote file name can not be empty. Please specify new remote file name.\n")
        raise SaproException("Local file name can not be empty. Please specify local file name.")

    requestBuffer = saproCommObj.CreateRequestHeaderPacketForFileOperForWrite(
        saproCommObj.getValue("PACKET_NS_FILE_OPER"), 5, oldRemoteFileName, newRemoteFileName, len(newRemoteFileName),
        0)

    saproCommObj.sock.send(requestBuffer, len(requestBuffer))

    replyBuf = saproCommObj.getReplyDataBuffer("WriteFile", "PACKET_NS_FILE_OPER", "PACKET_NS_REPLY_FILE_OPER")

    index = 0

    status = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    fileName = struct.unpack_from("%ds" % fileNameLen, replyBuf, index)[0].decode()
    index += fileNameLen

    errMsgLen = struct.unpack_from(">h", replyBuf, index)[0]
    index += struct.calcsize(">h")

    errMsg = struct.unpack_from("%ds" % errMsgLen, replyBuf, index)[0].decode()
    index += errMsgLen

    if status != saproCommObj.getFileOperStatus("FILE_OPER_OK"):
        print(errMsg)
        return False

    return True


# exported
def WriteFile(saproCommObj, remoteFileName, localFileName):
    """
        This is to send local file's data to  sapns server.

        Args:

            saproCommObj  : An instance of SaproCommunication class.
            remoteFileName: Name of the file to be created at sapns server
                            to store following files's data.
            localFileName : Source file to be uploaded on sapns server

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "WriteFile : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteFileName == ""):
        print("Remote file name can not be empty. Please specify remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    if (localFileName == ""):
        print("Local file name can not be empty. Please specify local file name.\n")
        raise SaproException("Local file name can not be empty. Please specify local file name.")

    fileContents = ""
    if os.path.exists(localFileName):
        with open(localFileName, 'rb') as fp:
            try:
                fileContents = fp.read()
            except IOError as err:
                raise SaproException(format(err))
    else:
        raise SaproException("Local File does not exist.")

    return WriteDataIntoFile(saproCommObj, remoteFileName, fileContents)


def WriteDataIntoFile(saproCommObj, remoteFileName, fileData):
    """
        This is to send local file's data to  sapns server.

        Args:

            saproCommObj  : An instance of SaproCommunication class.
            remoteFileName: Name of the file to be created at sapns server
                            to store following data.
            fileData      : Data to be uploaded on sapns server

        Returns:

            True on Success, False on Failure.
    """

    if saproCommObj is None:
        print("Sapro Communication Object is not initiated\n")
        raise SaproException(
            "WriteDataIntoFile : Sapro Communication Object is not instantiated. Please create object of SaproCommunication class and call initConnection function")

    if (remoteFileName == ""):
        print("Remote file name can not be empty. Please specify remote file name.\n")
        raise SaproException("Remote file name can not be empty. Please specify remote file name.")

    if (fileData == ""):
        print("No data specified to upload. Please specify fileData.\n")
        raise SaproException("No data specified to upload. Please specify fileData.")

    fileContents = fileData

    remainingBytes = len(fileContents)
    fileOffset = 0
    offsetIndex = 0
    MAXPACKETBUFLEN = 4096
    while remainingBytes > 0:
        bytesLen = remainingBytes;
        if remainingBytes > MAXPACKETBUFLEN:
            bytesLen = MAXPACKETBUFLEN
        subStr = fileContents[offsetIndex:(offsetIndex + bytesLen)]
        offsetIndex += bytesLen

        requestBuffer = saproCommObj.CreateRequestHeaderPacketForFileOperForWrite(
            saproCommObj.getValue("PACKET_NS_FILE_OPER"), 2, remoteFileName, subStr, bytesLen, fileOffset)

        remainingBytes -= bytesLen
        fileOffset += bytesLen

        saproCommObj.sock.send(requestBuffer, len(requestBuffer))

        replyBuf = saproCommObj.getReplyDataBuffer("WriteFile", "PACKET_NS_FILE_OPER", "PACKET_NS_REPLY_FILE_OPER")

        index = 0

        status = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileNameLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        fileName = struct.unpack_from("%ds" % fileNameLen, replyBuf, index)[0].decode()
        index += fileNameLen

        errMsgLen = struct.unpack_from(">h", replyBuf, index)[0]
        index += struct.calcsize(">h")

        errMsg = struct.unpack_from("%ds" % errMsgLen, replyBuf, index)[0].decode()
        index += errMsgLen

        if status != saproCommObj.getFileOperStatus("FILE_OPER_OK"):
            print(errMsg)
            return False

    return True
