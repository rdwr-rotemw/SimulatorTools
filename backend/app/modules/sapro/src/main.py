
"""
GetMapDevListFromServer
GetDeviceStatusFromMap
GetLicenseInfo
GetFullLicenseInfo
"""
from backend.app.modules.sapro.src import saproCommunication, saproMapFunctions, saproStatistics
from backend.app.modules.sapro.src.saproException import SaproException

sapro = saproCommunication.SaproCommunication()
try:
    #sapro.initConnection("192.168.2.121",2100)
    sapro.initConnection("127.0.0.1",2100)
    # sapro.createPacket(12,"sapro")
    #sapro.createRequestHeaderPacket(5,60)  
    #saproMapFunctions.getMapListFromServer(sapro)
    minfo = saproMapFunctions.getMapInfo(sapro,"../map/sample.map")#"../map/small_lan.map") 
    #list1 = saproStatistics.GetAllProtocolStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetAllIOTStatisticsFromMap(sapro,"../map/sample.map")
    
    list1 = saproStatistics.GetCoapStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetMqttSNStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetBacnetStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetMqttStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetHttpCLStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetTelnetSshTl1StatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetMqttBKStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetModbusStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetAllIOTStatisticsFromMap(sapro,"../map/sample.map")
    #list1 = saproStatistics.GetPerfStatFromMap(sapro,"../map/sample.map")
    
    #replyStr = saproMapFunctions.GetStatsFromMap(sapro,"../map/sample.map")
    #replyStr = saproMapFunctions.GetMapDevListFromServer(sapro)

    #replyStr = saproMapFunctions.SendStartCmdToMap(sapro,"../map/sample.map")
    #print("SendStartCmdToMap Reply",replyStr) 
    #replyStr = saproMapFunctions.SendStopCmdToMap(sapro,"../map/sample.map")
    #replyStr = saproMapFunctions.SendScenarioFileToMap(sapro,"/opt/sapro/map/sample.map","/opt/sapro/scenarios/lnkdnmap.tcl")
    #replyStr = saproMapFunctions.SendStartCmdToMapWithLogfile(sapro,"../map/sample.map","../log/sample.log")
    #replyStr =  saproMapFunctions.SendAsyncStartCmdToMap(sapro,"../map/sample.map")
    #replyStr =  saproMapFunctions.SendAsyncStartCmdToMapWithLogfile(sapro,"../map/sample.map","../log/sample.log")
    #replyStr =  saproMapFunctions.SendFastStopCmdToMap(sapro,"../map/sample.map")
    #replyStr =  saproMapFunctions.SendStopSetupScriptToMap(sapro,"../map/sample.map","../tcl/dev1.tcl")
    #replyStr =  saproMapFunctions.SendSetupScriptToMap(sapro,"../map/sample.map","../tcl/dev1.tcl")
    #replyStr =  saproMapFunctions.GetStatsFromMapPort(sapro,minfo.mapPort)
    #replyStr =  saproMapFunctions.SendAddDevCmdToMap(sapro,"../map/sample.map","../map/sample1.map")
    #replyStr =  saproMapFunctions.SendDeleteDevCmdToMap(sapro,"../map/sample.map","../map/sample1.map")

    
    #replyStr = saproDeviceFunctions.GetDeviceStatusFromMap(sapro,"/opt/sapro/map/sample.map","192.168.16.10")
    #replyStr = saproDeviceFunctions.SendScenarioCmdToDevice(sapro,"/opt/sapro/map/sample.map","192.168.16.10","/opt/sapro/scenarios/lnkdnmap.tcl")
    #replyStr = saproDeviceFunctions.GetDeviceListOfMap(sapro,minfo.mapPort)
    #replyStr = saproDeviceFunctions.SendStartCmdToDevice(sapro,"../map/sample.map","192.168.16.10")
    #replyStr = saproDeviceFunctions.SendStopCmdToDevice(sapro,"../map/sample.map","192.168.16.10")
    #replyStr = saproDeviceFunctions.SendRestartCmdToDevice(sapro,"../map/sample.map","192.168.16.10")
    #replyStr = saproDeviceFunctions.FindDevice(sapro,"192.168.16.10")
    #replyStr = saproDeviceFunctions.GetTagDeviceList(sapro,minfo.mapPort)
    #saproDeviceFunctions.GetTagDeviceListInfo(saproCommObj, mapName)
    #print(" Reply",replyStr)
    print(" Reply",list1)
except SaproException as e:
    print ("Main",e.toString())
    

