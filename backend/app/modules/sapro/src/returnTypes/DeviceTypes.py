class DeviceTypes:
    def __init__(self):
        self.types = {}

    def add_variable(self, name, value):
        self.types[name] = value

    def get_variable(self, name):
        return self.types.get(name)


types_container = DeviceTypes()

Alteon1 = F"<DeviceMap\n" \
          "        Release = \"11.0\"\n" \
          "        Description = \"\"\n" \
          "        UserData = \"\"\n" \
          "        SetupFile = \"\"\n" \
          "        Interface = \"\"\n" \
          "        Separator = \"\"\n" \
          "        StartInterfaceNum = \"0\"\n" \
          "        Username = \"\">\n" \
          "        <Device>\n" \
          "                <General\n" \
          "                        Name = \"<ip>\"\n" \
          "                        MultiHome = \"1\"\n" \
          "                        DHCP = \"0\"\n" \
          "                        SubnetMask = \"255.255.0.0\"\n" \
          "                        MacAddress = \"\"\n" \
          "                        Interface = \"\"\n" \
          "                        UserData = \"\"\n" \
          "                        TopologyData = \"\"\n" \
          "                        DisplayTag = \"\"\n" \
          "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
          "                />\n" \
          "                <Snmp\n" \
          "                        ReadCommunity = \"public\"\n" \
          "                        WriteCommunity = \"private\"\n" \
          "                        MibFile = \"/opt/sapro/cmf/Alteon_32.4.0.0.cmf\"\n" \
          "                        AgentFile = \"/opt/sapro/var/Alteon_32.4.0.0.cva\"\n" \
          "                        TrapMgr = \"\"\n" \
          "                        SnmpStr = \"V1V2V3\"\n" \
          "                        ResponseDelay = \"0\"\n" \
          "                        MtuSize = \"1500\"\n" \
          "                        SnmpPort = \"161\"\n" \
          "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
          "                        UserName = \"noAuthUser\"\n" \
          "                />\n" \
          "                <Soap\n" \
          "                        SoapHttpPort = \"80\"\n" \
          "                        SoapHttpsPort = \"443\"\n" \
          "                        XmlHttpsType = \"2\"\n" \
          "                        SoapModFile = \"/opt/sapro/xml/Alteon1.xmf\"\n" \
          "                        SoapContentType = \"\"\n" \
          "                />\n" \
          "        </Device>\n" \
          "</DeviceMap>"

Alteon2 = F"<DeviceMap\n" \
          "        Release = \"11.0\"\n" \
          "        Description = \"\"\n" \
          "        UserData = \"\"\n" \
          "        SetupFile = \"\"\n" \
          "        Interface = \"\"\n" \
          "        Separator = \"\"\n" \
          "        StartInterfaceNum = \"0\"\n" \
          "        Username = \"\">\n" \
          "        <Device>\n" \
          "                <General\n" \
          "                        Name = \"<ip>\"\n" \
          "                        MultiHome = \"1\"\n" \
          "                        DHCP = \"0\"\n" \
          "                        SubnetMask = \"255.255.0.0\"\n" \
          "                        MacAddress = \"\"\n" \
          "                        Interface = \"\"\n" \
          "                        UserData = \"\"\n" \
          "                        TopologyData = \"\"\n" \
          "                        DisplayTag = \"\"\n" \
          "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
          "                />\n" \
          "                <Snmp\n" \
          "                        ReadCommunity = \"public\"\n" \
          "                        WriteCommunity = \"private\"\n" \
          "                        MibFile = \"/opt/sapro/cmf/Alteon_32.4.0.0.cmf\"\n" \
          "                        AgentFile = \"/opt/sapro/var/Alteon_32.4.0.0.cva\"\n" \
          "                        TrapMgr = \"\"\n" \
          "                        SnmpStr = \"V1V2V3\"\n" \
          "                        ResponseDelay = \"0\"\n" \
          "                        MtuSize = \"1500\"\n" \
          "                        SnmpPort = \"161\"\n" \
          "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
          "                        UserName = \"noAuthUser\"\n" \
          "                />\n" \
          "                <Soap\n" \
          "                        SoapHttpPort = \"80\"\n" \
          "                        SoapHttpsPort = \"443\"\n" \
          "                        XmlHttpsType = \"2\"\n" \
          "                        SoapModFile = \"/opt/sapro/xml/Alteon2.xmf\"\n" \
          "                        SoapContentType = \"\"\n" \
          "                />\n" \
          "        </Device>\n" \
          "</DeviceMap>"

Alteon3 = F"<DeviceMap\n" \
          "        Release = \"11.0\"\n" \
          "        Description = \"\"\n" \
          "        UserData = \"\"\n" \
          "        SetupFile = \"\"\n" \
          "        Interface = \"\"\n" \
          "        Separator = \"\"\n" \
          "        StartInterfaceNum = \"0\"\n" \
          "        Username = \"\">\n" \
          "        <Device>\n" \
          "                <General\n" \
          "                        Name = \"<ip>\"\n" \
          "                        MultiHome = \"1\"\n" \
          "                        DHCP = \"0\"\n" \
          "                        SubnetMask = \"255.255.0.0\"\n" \
          "                        MacAddress = \"\"\n" \
          "                        Interface = \"\"\n" \
          "                        UserData = \"\"\n" \
          "                        TopologyData = \"\"\n" \
          "                        DisplayTag = \"\"\n" \
          "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
          "                />\n" \
          "                <Snmp\n" \
          "                        ReadCommunity = \"public\"\n" \
          "                        WriteCommunity = \"private\"\n" \
          "                        MibFile = \"/opt/sapro/cmf/Alteon_32.4.0.0.cmf\"\n" \
          "                        AgentFile = \"/opt/sapro/var/Alteon_32.4.0.0.cva\"\n" \
          "                        TrapMgr = \"\"\n" \
          "                        SnmpStr = \"V1V2V3\"\n" \
          "                        ResponseDelay = \"0\"\n" \
          "                        MtuSize = \"1500\"\n" \
          "                        SnmpPort = \"161\"\n" \
          "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
          "                        UserName = \"noAuthUser\"\n" \
          "                />\n" \
          "                <Soap\n" \
          "                        SoapHttpPort = \"80\"\n" \
          "                        SoapHttpsPort = \"443\"\n" \
          "                        XmlHttpsType = \"2\"\n" \
          "                        SoapModFile = \"/opt/sapro/xml/Alteon_3.xmf\"\n" \
          "                        SoapContentType = \"\"\n" \
          "                />\n" \
          "        </Device>\n" \
          "</DeviceMap>"

Alteon_IPv6_1 = "<DeviceMap\n" \
                "        Release = \"11.0\"\n" \
                "        Description = \"\"\n" \
                "        UserData = \"\"\n" \
                "        SetupFile = \"\"\n" \
                "        Interface = \"\"\n" \
                "        Separator = \"\"\n" \
                "        StartInterfaceNum = \"0\"\n" \
                "        Username = \"\">\n" \
                "        <Device>\n" \
                "                <General\n" \
                "                        Name = \"<ip>\"\n" \
                "                        MultiHome = \"1\"\n" \
                "                        DHCP = \"0\"\n" \
                "                        SubnetMask = \"64\"\n" \
                "                        MacAddress = \"\"\n" \
                "                        Interface = \"\"\n" \
                "                        UserData = \"\"\n" \
                "                        TopologyData = \"\"\n" \
                "                        DisplayTag = \"\"\n" \
                "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
                "                        CommonDataFile = \"\"\n" \
                "                />\n" \
                "                <Snmp\n" \
                "                        ReadCommunity = \"public\"\n" \
                "                        WriteCommunity = \"private\"\n" \
                "                        MibFile = \"/opt/sapro/cmf/Alteon_IPv6.cmf\"\n" \
                "                        AgentFile = \"/opt/sapro/var/Alteon_IPv6.var\"\n" \
                "                        TrapMgr = \"\"\n" \
                "                        SnmpStr = \"V1V2V3\"\n" \
                "                        ResponseDelay = \"0\"\n" \
                "                        MtuSize = \"1500\"\n" \
                "                        SnmpPort = \"161\"\n" \
                "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
                "                        UserName = \"noAuthUser\"\n" \
                "                />\n" \
                "                <Soap\n" \
                "                        SoapHttpPort = \"80\"\n" \
                "                        SoapHttpsPort = \"443\"\n" \
                "                        XmlHttpsType = \"2\"\n" \
                "                        SoapModFile = \"/opt/sapro/xml/Alteon_IPv6_1.xmf\"\n" \
                "                        SoapContentType = \"\"\n" \
                "                />\n" \
                "        </Device>\n" \
                "</DeviceMap>"

Alteon_IPv6_2 = "<DeviceMap\n" \
                "        Release = \"11.0\"\n" \
                "        Description = \"\"\n" \
                "        UserData = \"\"\n" \
                "        SetupFile = \"\"\n" \
                "        Interface = \"\"\n" \
                "        Separator = \"\"\n" \
                "        StartInterfaceNum = \"0\"\n" \
                "        Username = \"\">\n" \
                "        <Device>\n" \
                "                <General\n" \
                "                        Name = \"<ip>\"\n" \
                "                        MultiHome = \"1\"\n" \
                "                        DHCP = \"0\"\n" \
                "                        SubnetMask = \"64\"\n" \
                "                        MacAddress = \"\"\n" \
                "                        Interface = \"\"\n" \
                "                        UserData = \"\"\n" \
                "                        TopologyData = \"\"\n" \
                "                        DisplayTag = \"\"\n" \
                "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
                "                        CommonDataFile = \"\"\n" \
                "                />\n" \
                "                <Snmp\n" \
                "                        ReadCommunity = \"public\"\n" \
                "                        WriteCommunity = \"private\"\n" \
                "                        MibFile = \"/opt/sapro/cmf/Alteon_IPv6.cmf\"\n" \
                "                        AgentFile = \"/opt/sapro/var/Alteon_IPv6.var\"\n" \
                "                        TrapMgr = \"\"\n" \
                "                        SnmpStr = \"V1V2V3\"\n" \
                "                        ResponseDelay = \"0\"\n" \
                "                        MtuSize = \"1500\"\n" \
                "                        SnmpPort = \"161\"\n" \
                "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
                "                        UserName = \"noAuthUser\"\n" \
                "                />\n" \
                "                <Soap\n" \
                "                        SoapHttpPort = \"80\"\n" \
                "                        SoapHttpsPort = \"443\"\n" \
                "                        XmlHttpsType = \"2\"\n" \
                "                        SoapModFile = \"/opt/sapro/xml/Alteon_IPv6_2.xmf\"\n" \
                "                        SoapContentType = \"\"\n" \
                "                />\n" \
                "        </Device>\n" \
                "</DeviceMap>"

Alteon_IPv6_3 = F"<DeviceMap\n" \
                "        Release = \"11.0\"\n" \
                "        Description = \"\"\n" \
                "        UserData = \"\"\n" \
                "        SetupFile = \"\"\n" \
                "        Interface = \"\"\n" \
                "        Separator = \"\"\n" \
                "        StartInterfaceNum = \"0\"\n" \
                "        Username = \"\">\n" \
                "        <Device>\n" \
                "                <General\n" \
                "                        Name = \"<ip>\"\n" \
                "                        MultiHome = \"1\"\n" \
                "                        DHCP = \"0\"\n" \
                "                        SubnetMask = \"64\"\n" \
                "                        MacAddress = \"\"\n" \
                "                        Interface = \"\"\n" \
                "                        UserData = \"\"\n" \
                "                        TopologyData = \"\"\n" \
                "                        DisplayTag = \"\"\n" \
                "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
                "                        CommonDataFile = \"\"\n" \
                "                />\n" \
                "                <Snmp\n" \
                "                        ReadCommunity = \"public\"\n" \
                "                        WriteCommunity = \"private\"\n" \
                "                        MibFile = \"/opt/sapro/cmf/Alteon_IPv6.cmf\"\n" \
                "                        AgentFile = \"/opt/sapro/var/Alteon_IPv6.var\"\n" \
                "                        TrapMgr = \"\"\n" \
                "                        SnmpStr = \"V1V2V3\"\n" \
                "                        ResponseDelay = \"0\"\n" \
                "                        MtuSize = \"1500\"\n" \
                "                        SnmpPort = \"161\"\n" \
                "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
                "                        UserName = \"noAuthUser\"\n" \
                "                />\n" \
                "                <Soap\n" \
                "                        SoapHttpPort = \"80\"\n" \
                "                        SoapHttpsPort = \"443\"\n" \
                "                        XmlHttpsType = \"2\"\n" \
                "                        SoapModFile = \"/opt/sapro/xml/Alteon_IPv6_3.xmf\"\n" \
                "                        SoapContentType = \"\"\n" \
                "                />\n" \
                "        </Device>\n" \
                "</DeviceMap>"

DP_8_30 = F"<DeviceMap\n" \
          "        Release = \"11.0\"\n" \
          "        Description = \"\"\n" \
          "        UserData = \"\"\n" \
          "        SetupFile = \"\"\n" \
          "        Interface = \"\"\n" \
          "        Separator = \"\"\n" \
          "        StartInterfaceNum = \"0\"\n" \
          "        Username = \"\">\n" \
          "        <Device>\n" \
          "                <General\n" \
          "                        Name = \"<ip>\"\n" \
          "                        MultiHome = \"1\"\n" \
          "                        DHCP = \"0\"\n" \
          "                        SubnetMask = \"255.255.0.0\"\n" \
          "                        MacAddress = \"\"\n" \
          "                        Interface = \"\"\n" \
          "                        UserData = \"\"\n" \
          "                        TopologyData = \"\"\n" \
          "                        DisplayTag = \"\"\n" \
          "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
          "                />\n" \
          "                <Snmp\n" \
          "                        ReadCommunity = \"public\"\n" \
          "                        WriteCommunity = \"private\"\n" \
          "                        MibFile = \"/opt/sapro/cmf/DP_8.30.cmf\"\n" \
          "                        AgentFile = \"/opt/sapro/var/DP_8.30.cva\"\n" \
          "                        TrapMgr = \"\"\n" \
          "                        SnmpStr = \"V1V2V3\"\n" \
          "                        ResponseDelay = \"0\"\n" \
          "                        MtuSize = \"1500\"\n" \
          "                        SnmpPort = \"161\"\n" \
          "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
          "                        UserName = \"noAuthUser\"\n" \
          "                />\n" \
          "                <SSH\n" \
          "                        SSHUserName = \"admin\"\n" \
          "                        SSHPassword = \"admin\"\n" \
          "                        SSHSCPBaseDir = \"/\"\n" \
          "                        SSHVersion = \"SSH-1.99-SSHSAPRO-4.3\"\n" \
          "                        SSHFile = \"/opt/sapro/telnet/DP_8.30.tel\"\n" \
          "                />\n" \
          "                <Soap\n" \
          "                        SoapHttpPort = \"80\"\n" \
          "                        SoapHttpsPort = \"8790\"\n" \
          "                        XmlHttpsType = \"2\"\n" \
          "                        SoapModFile = \"/opt/sapro/xml/DP_sim_8.28_empty_json.xmf\"\n" \
          "                        SoapContentType = \"\"\n" \
          "                />\n" \
          "        </Device>\n" \
          "</DeviceMap>"

LP = F"<DeviceMap\n" \
     "        Release = \"11.0\"\n" \
     "        Description = \"\"\n" \
     "        UserData = \"\"\n" \
     "        SetupFile = \"\"\n" \
     "        Interface = \"\"\n" \
     "        Separator = \"\"\n" \
     "        StartInterfaceNum = \"0\"\n" \
     "        Username = \"\">\n" \
     "        <Device>\n" \
     "                <General\n" \
     "                        Name = \"<ip>\"\n" \
     "                        MultiHome = \"1\"\n" \
     "                        DHCP = \"0\"\n" \
     "                        SubnetMask = \"255.255.0.0\"\n" \
     "                        MacAddress = \"\"\n" \
     "                        Interface = \"\"\n" \
     "                        UserData = \"\"\n" \
     "                        TopologyData = \"\"\n" \
     "                        DisplayTag = \"\"\n" \
     "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
     "                />\n" \
     "                <Snmp\n" \
     "                        ReadCommunity = \"public\"\n" \
     "                        WriteCommunity = \"private\"\n" \
     "                        MibFile = \"/opt/sapro/cmf/linkproof.cmf\"\n" \
     "                        AgentFile = \"/opt/sapro/var/LP_32.6.5.0.cva\"\n" \
     "                        TrapMgr = \"\"\n" \
     "                        SnmpStr = \"V1V2V3\"\n" \
     "                        ResponseDelay = \"0\"\n" \
     "                        MtuSize = \"1500\"\n" \
     "                        SnmpPort = \"161\"\n" \
     "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
     "                        UserName = \"noAuthUser\"\n" \
     "                />\n" \
     "                <Soap\n" \
     "                        SoapHttpPort = \"80\"\n" \
     "                        SoapHttpsPort = \"443\"\n" \
     "                        XmlHttpsType = \"0\"\n" \
     "                        SoapModFile = \"/opt/sapro/xml/Alteon_LP_32.6.5.0_jason_xml_output.xmf\"\n" \
     "                        SoapContentType = \"\"\n" \
     "                />\n" \
     "        </Device>\n" \
     "</DeviceMap>"

DP_10_5 = F"<DeviceMap\n" \
          "        Release = \"11.0\"\n" \
          "        Description = \"\"\n" \
          "        UserData = \"\"\n" \
          "        SetupFile = \"\"\n" \
          "        Interface = \"\"\n" \
          "        Separator = \"\"\n" \
          "        StartInterfaceNum = \"0\"\n" \
          "        Username = \"\">\n" \
          "        <Device>\n" \
          "                <General\n" \
          "                        Name = \"<ip>\"\n" \
          "                        MultiHome = \"1\"\n" \
          "                        DHCP = \"0\"\n" \
          "                        SubnetMask = \"64\"\n" \
          "                        MacAddress = \"\"\n" \
          "                        Interface = \"\"\n" \
          "                        UserData = \"\"\n" \
          "                        TopologyData = \"\"\n" \
          "                        DisplayTag = \"\"\n" \
          "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
          "                        CommonDataFile = \"\"\n" \
          "                />\n" \
          "                <Snmp\n" \
          "                        ReadCommunity = \"public\"\n" \
          "                        WriteCommunity = \"private\"\n" \
          "                        MibFile = \"/opt/sapro/cmf/DP_10-5.cmf\"\n" \
          "                        AgentFile = \"/opt/sapro/var/DP_10-5.var\"\n" \
          "                        TrapMgr = \"\"\n" \
          "                        SnmpStr = \"V1V2V3\"\n" \
          "                        ResponseDelay = \"0\"\n" \
          "                        MtuSize = \"1500\"\n" \
          "                        SnmpPort = \"161\"\n" \
          "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
          "                        UserName = \"noAuthUser\"\n" \
          "                />\n" \
          "                <Soap\n" \
          "                        SoapHttpPort = \"80\"\n" \
          "                        SoapHttpsPort = \"8790\"\n" \
          "                        XmlHttpsType = \"2\"\n" \
          "                        SoapModFile = \"/opt/sapro/xml/DNS_test_endpoint.xmf\"\n" \
          "                        SoapContentType = \"\"\n" \
          "                />\n" \
          "        </Device>\n" \
          "</DeviceMap>"

DP_10_5_IPv6 = F"<DeviceMap\n" \
               "        Release = \"11.0\"\n" \
               "        Description = \"\"\n" \
               "        UserData = \"\"\n" \
               "        SetupFile = \"\"\n" \
               "        Interface = \"\"\n" \
               "        Separator = \"\"\n" \
               "        StartInterfaceNum = \"0\"\n" \
               "        Username = \"\">\n" \
               "        <Device>\n" \
               "                <General\n" \
               "                        Name = \"<ip>\"\n" \
               "                        MultiHome = \"1\"\n" \
               "                        DHCP = \"0\"\n" \
               "                        SubnetMask = \"255.255.255.0\"\n" \
               "                        MacAddress = \"\"\n" \
               "                        Interface = \"\"\n" \
               "                        UserData = \"\"\n" \
               "                        TopologyData = \"\"\n" \
               "                        DisplayTag = \"\"\n" \
               "                        ModelingFile = \"/opt/sapro/tcl/varchange.tcl\"\n" \
               "                        CommonDataFile = \"\"\n" \
               "                />\n" \
               "                <Snmp\n" \
               "                        ReadCommunity = \"public\"\n" \
               "                        WriteCommunity = \"private\"\n" \
               "                        MibFile = \"/opt/sapro/cmf/DP_10-5.cmf\"\n" \
               "                        AgentFile = \"/opt/sapro/var/DP_10-5.var\"\n" \
               "                        TrapMgr = \"\"\n" \
               "                        SnmpStr = \"V1V2V3\"\n" \
               "                        ResponseDelay = \"0\"\n" \
               "                        MtuSize = \"1500\"\n" \
               "                        SnmpPort = \"161\"\n" \
               "                        SecurityLevel = \"NoAuthNoPriv\"\n" \
               "                        UserName = \"noAuthUser\"\n" \
               "                />\n" \
               "                <Soap\n" \
               "                        SoapHttpPort = \"80\"\n" \
               "                        SoapHttpsPort = \"8790\"\n" \
               "                        XmlHttpsType = \"2\"\n" \
               "                        SoapModFile = \"/opt/sapro/xml/DNS_test_endpoint.xmf\"\n" \
               "                        SoapContentType = \"\"\n" \
               "                />\n" \
               "        </Device>\n" \
               "</DeviceMap>"

types_container.add_variable("Alteon1", Alteon1)
types_container.add_variable("Alteon2", Alteon2)
types_container.add_variable("Alteon3", Alteon3)
types_container.add_variable("Alteon_IPv6_1", Alteon_IPv6_1)
types_container.add_variable("Alteon_IPv6_2", Alteon_IPv6_2)
types_container.add_variable("Alteon_IPv6_3", Alteon_IPv6_3)
types_container.add_variable("DP_8_30", DP_8_30)
types_container.add_variable("DP_10_5", DP_10_5)
types_container.add_variable("DP_10_5_IPv6", DP_10_5_IPv6)
types_container.add_variable("LP", LP)
