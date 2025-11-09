# -*- coding: utf-8 -*-


class DeviceInfoBase:
    """
        This is a base class. It contains device's name.
    """

    def __init__(self, devName):
        self.devName = devName


class DeviceInfo(DeviceInfoBase):
    """
        This is derived from DeviceInfoBase. It contains information related to
        device status and device's port.
    """

    def __init__(self, devName, devStat, port):
        DeviceInfoBase.__init__(self,devName)
        self.devStatus = devStat
        self.devPort = port


class DeviceTagInfo(DeviceInfoBase):
    """
        This is derived from DeviceInfoBase. It contains information related to
        tag name assigned to this device.
    """

    def __init__(self, devName, devStat, tagName):
        DeviceInfoBase.__init__(self,devName)
        self.devStatus = devStat
        self.tag = tagName


class FoundDeviceInfo(DeviceInfoBase):
    """
        This is derived from DeviceInfoBase. It contains information related to
        the device's map and device's status.
    """

    def __init__(self, mapName, devName, devStat):
        DeviceInfoBase.__init__(self,devName)
        self.mapName = mapName
        self.devStatus = devStat


class NetFlowStats(DeviceInfoBase):

    """
        This is derived from DeviceInfoBase. It contains device's netflow statistics.
    """

    def __init__(self, devName, pktCnt, netFlow):
        DeviceInfoBase.__init__(self,devName)
        self.netFlowPktCnt = pktCnt
        self.netFlowFlow = netFlow

