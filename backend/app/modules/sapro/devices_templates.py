from enum import Enum


class DevicesTemplates(Enum):
    """Device templates for SAPRO simulator configuration"""

    ALTEON1 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.0.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_32.4.0.0.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_32.4.0.0.cva"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon1.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    ALTEON2 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.0.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_32.4.0.0.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_32.4.0.0.cva"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon2.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    ALTEON3 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.0.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_32.4.0.0.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_32.4.0.0.cva"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon_3.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    ALTEON_IPV6_1 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "64"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                        CommonDataFile = ""
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_IPv6.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_IPv6.var"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon_IPv6_1.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    ALTEON_IPV6_2 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "64"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                        CommonDataFile = ""
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_IPv6.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_IPv6.var"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon_IPv6_2.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    ALTEON_IPV6_3 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "64"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                        CommonDataFile = ""
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/Alteon_IPv6.cmf"
                        AgentFile = "/opt/sapro/var/Alteon_IPv6.var"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/Alteon_IPv6_3.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    DP_8_30 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.0.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/DP_8.30.cmf"
                        AgentFile = "/opt/sapro/var/DP_8.30.cva"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <SSH
                        SSHUserName = "admin"
                        SSHPassword = "admin"
                        SSHSCPBaseDir = "/"
                        SSHVersion = "SSH-1.99-SSHSAPRO-4.3"
                        SSHFile = "/opt/sapro/telnet/DP_8.30.tel"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "8790"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/DP_sim_8.28_empty_json.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    LP = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.0.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/linkproof.cmf"
                        AgentFile = "/opt/sapro/var/LP_32.6.5.0.cva"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "443"
                        XmlHttpsType = "0"
                        SoapModFile = "/opt/sapro/xml/Alteon_LP_32.6.5.0_jason_xml_output.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    DP_10_5 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.255.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                        CommonDataFile = ""
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/DP_10-5.cmf"
                        AgentFile = "/opt/sapro/var/DP_10-5.var"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "8790"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/empty_json.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    DPX_10_6 = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
        <Device>
                <General
                        Name = "<ip>"
                        MultiHome = "1"
                        DHCP = "0"
                        SubnetMask = "255.255.255.0"
                        MacAddress = ""
                        Interface = ""
                        UserData = ""
                        TopologyData = ""
                        DisplayTag = ""
                        ModelingFile = "/opt/sapro/tcl/varchange.tcl"
                        CommonDataFile = ""
                />
                <Snmp
                        ReadCommunity = "public"
                        WriteCommunity = "public"
                        MibFile = "/opt/sapro/cmf/DP_10_6.cmf"
                        AgentFile = "/opt/sapro/var/DPX_10-6.var"
                        TrapMgr = ""
                        SnmpStr = "V1V2V3"
                        ResponseDelay = "0"
                        MtuSize = "1500"
                        SnmpPort = "161"
                        SecurityLevel = "NoAuthNoPriv"
                        UserName = "noAuthUser"
                />
                <SSH
                        SSHUserName = "radware"
                        SSHPassword = "radware1"
                        SSHSCPBaseDir = "/tmp"
                        SSHVersion = "SSH-1.99-SSHSAPRO-4.3"
                        SSHFile = "/opt/sapro/telnet/DPX_2.tel"
                />
                <Soap
                        SoapHttpPort = "80"
                        SoapHttpsPort = "8790"
                        XmlHttpsType = "2"
                        SoapModFile = "/opt/sapro/xml/empty_json.xmf"
                        SoapContentType = ""
                />
        </Device>
</DeviceMap>"""

    def get_template(self) -> str:
        """Get the template string for this device."""
        return self.value


def get_template_by_name(version: str) -> str:
    """
    Retrieve device template by version name.

    Args:
        version: Device version name (e.g., 'ALTEON1', 'DP_8_30', 'DPX_10_6')

    Returns:
        The XML template string for the requested device version.

    Raises:
        ValueError: If the version is not found in available templates.

    Example:
        >>> template = get_template_by_name('ALTEON1')
    """
    version = version.upper()
    try:
        return DevicesTemplates[version].value
    except KeyError:
        available = ', '.join([v.name for v in DevicesTemplates])
        raise ValueError(
            f"Unknown device version: {version}\n"
            f"Available versions: {available}"
        )


def list_available_templates() -> list:
    """Return a list of all available device versions."""
    return [v.name for v in DevicesTemplates]
