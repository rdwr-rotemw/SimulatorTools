from collections import namedtuple
"""
    'devStatsInfo' is a tuple that holds name of the device and it's all
    statistics.
"""
devStatsInfo = namedtuple('devStatsInfo', ['deviceName', 'inputPackets','getRequests','getnextrequests','setrequests','numResponses','getBulks','trapno','syslogno'])
telnetSSHTL1StatsInfo = namedtuple('telnetSSHTL1StatsInfo', \
                                    ['devName', 'numActiveTelnetSessionsPkts',\
                                    'numTelnetSessionsPkts', 'numTelnetCmdPkts',\
                                    'numSSHSessionsPkts', 'numSSHCmdPkts', \
                                    'numTL1SessionsPkts', 'numTL1CmdPkts',\
                                    'numNetFlowSentPkts'])
devNetflowinfo = namedtuple('devNetflowinfo', ['deviceName', 'numPublishes','numPings',\
                                                'numRetries','numAcks','numAvgLatency'])
httpCLStatInfo = namedtuple('httpCLStatInfo', ['deviceName', 'numTotalRequests','numTotalResponses'])
bacnetStatInfo = namedtuple('bacnetStatInfo', ['deviceName', 'numTotalRequests','numTotalResponses'])
coapStatInfo = namedtuple('coapStatInfo', ['deviceName', 'numTotalRequests','numTotalResponses',\
                                            'numGets','numPosts','numPuts',
                                            'numDeletes','numNotifications'])
mqttSNStatInfo = namedtuple('mqttSNStatInfo', ['deviceName', 'numPublishes','numPings',\
                                            'numRetries','numAcks','numAvgLatency'])
modbusStatInfo = namedtuple('modbusStatInfo', ['deviceName', 'numActiveConnections','numSessions','numCommands'])
perfStatInfo = namedtuple('perfStatInfo', ['deviceName', 'numRequest',\
                                            'numMinResp','numMaxResp','numAvgResp','numMaxQueueLength'])
mqttUserStatInfo = namedtuple('mqttUserStatInfo', ['deviceName', 'numStat','label','userstatval'])
allIOTStatInfo = namedtuple('allIOTStatInfo', ['deviceName', 'coapReqPkts','coapRespPkts',\
                                            'mqttPubPkts','mqttAvgLatPkts',\
                                            'mqttSnPubPkts','mqttSnAvgLatPkts',\
                                            'mqttBrPubPkts','mqttBrAvgLatPkts',\
                                            'modbusSessionPkts','modbusCommandPkts',\
                                            'httpCLRequests','httpCLResponses',\
                                            'bacnetRequests','bacnetResponses',\
                                            ])
allProtocolStatInfo = namedtuple('allProtocolStatInfo',[
                            'name' ,
                            'numReqPkts' ,
                            'numRespPkts',
                            'numTrapPkts',
                            'numTelnetSessionPkts' ,
                            'numTelnetCmdPkts' ,
                            'numSSHSessionPkts',
                            'numSSHCmdPkts' ,
                            'numTL1SessionPkts' ,
                            'numTL1CmdPkts' ,
                            'numNetflowSentPkts' ,
                            'numNetflowPkts' ,
                            'numActSoapSessionPkts' ,
                            'numSoapSessionPkts' ,
                            'numSoapCommandPkts' ,
                            'numActCloudSessionPkts' ,
                            'numCloudSessionPkts' ,
                            'numCloudCommandPkts' ,
                            'numCoapReqPkts' ,
                            'numCoapRespPkts',
                            'numMqttPublishes',
                            'numMqttAcks',
                            'numModbuSessionPkts',
                            'numModbuCmdPkts' ,
                            'numHttpClientReqPkts' ,
                            'numHttpClientRespPkts',
                            'numBacnetReqPkts' ,
                            'numBacnetRespPkts',
                            'numActNetconfSessionPkts' ,
                            'numNetconfSessionPkts' ,
                            'numNetconfCmdPkts' ,
                            'numMaxQueueLenPkts',
                            'numMinRespTimePkts',
                            'numMaxRespTimePkts',
                            'numStopwatchReqPkts',
                            'numAvgRespTimePkts' ])

