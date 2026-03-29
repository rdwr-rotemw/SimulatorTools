"""Constants for the OID Compiler module."""

# MIB/SNMP syntax -> CMF syntax normalization
SYNTAX_MAP = {
    "INTEGER": "Integer",
    "Integer32": "Integer",
    "Unsigned32": "Gauge",
    "Counter32": "Counter",
    "Counter64": "Counter64",
    "Gauge32": "Gauge",
    "TimeTicks": "TimeTicks",
    "OCTET STRING": "OctetString",
    "DisplayString": "OctetString",
    "SnmpAdminString": "OctetString",
    "PhysAddress": "OctetString",
    "MacAddress": "OctetString",
    "TruthValue": "Integer",
    "RowStatus": "Integer",
    "EntryStatus": "Integer",
    "TestAndIncr": "Integer",
    "StorageType": "Integer",
    "IpAddress": "IpAddress",
    "NetworkAddress": "IpAddress",
    "OBJECT IDENTIFIER": "ObjectID",
    "Opaque": "Opaque",
    "BITS": "Bits",
    # Radware-specific textual conventions
    "FeatureStatus": "Integer",
    "Ipv6Address": "OctetString",
    "Ipv6AddressPrefix": "OctetString",
    "TDomain": "ObjectID",
    "TAddress": "OctetString",
    "SnmpEngineID": "OctetString",
    "SnmpSecurityModel": "Integer",
    "SnmpMessageProcessingModel": "Integer",
    "SnmpSecurityLevel": "Integer",
    "SnmpTagList": "OctetString",
    "SnmpTagValue": "OctetString",
    "TimeInterval": "Integer",
    "AutonomousType": "ObjectID",
    "KeyChange": "OctetString",
}

# Default ranges when MIB doesn't specify one
DEFAULT_RANGES = {
    "Integer": (-2147483648, 2147483647),
    "Counter": (0, 4294967295),
    "Counter64": (0, 18446744073709551615),
    "Gauge": (0, 4294967295),
    "TimeTicks": (0, 4294967295),
    "OctetString": (0, 255),
    "IpAddress": (0, 0),
    "ObjectID": (0, 0),
    "Bits": (0, 0),
    "Opaque": (0, 0),
}

# Default value info for Read-Only variables
RO_DEFAULTS = {
    "Counter": "randomup(1000, 100)",
    "Counter64": "randomup(1000, 100)",
    "Gauge": "fixed(1000)",
    "OctetString": "fixed({label})",
    "TimeTicks": "clock(1000)",
    "Integer": "fixed(1)",
    "IpAddress": "fixed(1.2.3.4)",
    "ObjectID": "fixed(1.2.3)",
    "Bits": "fixed(0x00)",
    "Opaque": "fixed(0x00)",
}

# Default value info for Read-Write variables
RW_DEFAULTS = {
    "Counter": "lastset(1000)",
    "Counter64": "lastset(1000)",
    "Gauge": "lastset(1000)",
    "OctetString": "lastset({label})",
    "TimeTicks": "lastset(1000)",
    "Integer": "lastset(1)",
    "IpAddress": "lastset(1.2.3.4)",
    "ObjectID": "lastset(1.2.3)",
    "Bits": "lastset(0x00)",
    "Opaque": "lastset(0x00)",
}

# Default value info for Index columns
INDEX_DEFAULTS = {
    "OctetString": '"abc"',
    "Integer": "1",
    "IpAddress": "1.2.3.4",
    "ObjectID": "1.2.3",
}

# Textual conventions that resolve to RowStatus
ROWSTATUS_TCS = {"RowStatus"}

# Textual conventions that resolve to EntryStatus (RMON)
ENTRYSTATUS_TCS = {"EntryStatus"}
