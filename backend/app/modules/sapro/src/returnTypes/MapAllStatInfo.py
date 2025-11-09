# -*- coding: utf-8 -*-
from collections import namedtuple
mapStatsInfo = namedtuple('mapStatsInfo', ['mapName', 'allinpackets', 'alldevresps', 'telnetsessions', 'telnetcommands', 'sshsessions', 'sshcommands', 'TL1sessions', 'TL1commands', 'netflowpkts', 'activesoapsessions', 'soapsessions', 'soapcommands', 'netflowpktcount', 'netflowflow'])
mapInfo = namedtuple('mapInfo',['mapName','hostName','mapPort','numRunningDevices'])