"""
Seed device templates into MongoDB on application startup.

Provides idempotent seeding of device templates from predefined XML definitions.
Templates are converted from XML to JSON structure and stored in the device_templates collection.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Union
import xml.etree.ElementTree as ET
from pymongo.database import Database

from backend.app.utils.logger import logger


# Complete template definitions from Java enum (excluding DP_10_5)
TEMPLATES_DATA = [
    {
        "name": "ALTEON1",
        "description": "Alteon 1 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.0.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl"/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_32.4.0.0.cmf" AgentFile="/opt/sapro/var/Alteon_32.4.0.0.cva" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon1.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "ALTEON2",
        "description": "Alteon 2 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.0.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl"/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_32.4.0.0.cmf" AgentFile="/opt/sapro/var/Alteon_32.4.0.0.cva" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon2.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "ALTEON3",
        "description": "Alteon 3 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.0.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl"/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_32.4.0.0.cmf" AgentFile="/opt/sapro/var/Alteon_32.4.0.0.cva" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon_3.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "ALTEON_IPV6_1",
        "description": "Alteon IPv6 1 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="64" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl" CommonDataFile=""/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_IPv6.cmf" AgentFile="/opt/sapro/var/Alteon_IPv6.var" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon_IPv6_1.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "ALTEON_IPV6_2",
        "description": "Alteon IPv6 2 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="64" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl" CommonDataFile=""/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_IPv6.cmf" AgentFile="/opt/sapro/var/Alteon_IPv6.var" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon_IPv6_2.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "ALTEON_IPV6_3",
        "description": "Alteon IPv6 3 Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="64" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl" CommonDataFile=""/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/Alteon_IPv6.cmf" AgentFile="/opt/sapro/var/Alteon_IPv6.var" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/Alteon_IPv6_3.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "DP_8_30",
        "description": "DefensePro 8.30",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.0.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl"/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/DP_8.30.cmf" AgentFile="/opt/sapro/var/DP_8.30.cva" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><SSH SSHUserName="admin" SSHPassword="admin" SSHSCPBaseDir="/" SSHVersion="SSH-1.99-SSHSAPRO-4.3" SSHFile="/opt/sapro/telnet/DP_8.30.tel"/><Soap SoapHttpPort="80" SoapHttpsPort="8790" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/DP_sim_8.28_empty_json.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "LP",
        "description": "LinkProof Load Balancer",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.0.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl"/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/linkproof.cmf" AgentFile="/opt/sapro/var/LP_32.6.5.0.cva" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><Soap SoapHttpPort="80" SoapHttpsPort="443" XmlHttpsType="0" SoapModFile="/opt/sapro/xml/Alteon_LP_32.6.5.0_jason_xml_output.xmf" SoapContentType=""/></Device></DeviceMap>'''
    },
    {
        "name": "DPX_10_6",
        "description": "DefensePro X 10.6",
        "xml": '''<DeviceMap Release="11.0" Description="" UserData="" SetupFile="" Interface="" Separator="" StartInterfaceNum="0" Username=""><Device><General Name="IP_PLACEHOLDER" MultiHome="1" DHCP="0" SubnetMask="255.255.255.0" MacAddress="" Interface="" UserData="" TopologyData="" DisplayTag="" ModelingFile="/opt/sapro/tcl/varchange.tcl" CommonDataFile=""/><Snmp ReadCommunity="public" WriteCommunity="public" MibFile="/opt/sapro/cmf/DP_10_6.cmf" AgentFile="/opt/sapro/var/DPX_10-6.var" TrapMgr="" SnmpStr="V1V2V3" ResponseDelay="0" MtuSize="1500" SnmpPort="161" SecurityLevel="NoAuthNoPriv" UserName="noAuthUser"/><SSH SSHUserName="radware" SSHPassword="radware1" SSHSCPBaseDir="/tmp" SSHVersion="SSH-1.99-SSHSAPRO-4.3" SSHFile="/opt/sapro/telnet/DPX_2.tel"/><Soap SoapHttpPort="80" SoapHttpsPort="8790" XmlHttpsType="2" SoapModFile="/opt/sapro/xml/dpx_sim.xmf" SoapContentType=""/></Device></DeviceMap>'''
    }
]


def _pascal_to_snake(name: str) -> str:
    """Convert PascalCase to snake_case.

    Examples:
        DeviceMap -> device_map
        HTTPPort -> http_port
        Name -> name
    """
    result = []
    for i, char in enumerate(name):
        if char.isupper():
            if i > 0 and (name[i - 1].islower() or (i < len(name) - 1 and name[i + 1].islower())):
                result.append('_')
            result.append(char.lower())
        else:
            result.append(char)
    return ''.join(result)


def _element_to_dict(element: ET.Element) -> Union[Dict[str, Any], str]:
    """Recursively convert an XML Element to a nested dictionary.

    Rules:
    - Element tag becomes dict key (converted to snake_case)
    - Element attributes become dict entries (converted to snake_case)
    - Nested child elements become nested dicts
    - Text content is preserved if present and non-whitespace

    Args:
        element: XML Element to convert

    Returns:
        Dictionary representation of the element
    """
    result: Dict[str, Any] = {}

    # Add attributes to dict (convert keys to snake_case)
    for attr_key, attr_val in element.attrib.items():
        snake_key = _pascal_to_snake(attr_key)
        result[snake_key] = attr_val

    # Process child elements
    children = list(element)
    if children:
        for child in children:
            child_tag = _pascal_to_snake(child.tag)
            child_dict = _element_to_dict(child)

            # If multiple children with same tag exist, create a list
            if child_tag in result:
                if not isinstance(result[child_tag], list):
                    result[child_tag] = [result[child_tag]]
                result[child_tag].append(child_dict)
            else:
                result[child_tag] = child_dict

    # Handle text content (if no children and has meaningful text)
    elif element.text and element.text.strip():
        return element.text.strip()

    return result


def xml_to_json_dict(xml_string: str) -> Dict[str, Any]:
    """Parse XML string and convert to nested JSON dictionary.

    Converts XML structure to a nested dictionary suitable for MongoDB storage.
    Element tags and attributes are converted from PascalCase to snake_case.

    Args:
        xml_string: XML string to parse

    Returns:
        Dictionary with structure {"device_map": {...}}

    Raises:
        ET.ParseError: If XML is malformed
    """
    root = ET.fromstring(xml_string.strip())
    root_tag = _pascal_to_snake(root.tag)
    return {root_tag: _element_to_dict(root)}


def seed_device_templates(mongo_db: Database) -> None:
    """Seed device templates into MongoDB if not already present (idempotent).

    Checks if templates already exist in the device_templates collection.
    If empty, inserts all predefined templates from TEMPLATES_DATA.

    Args:
        mongo_db: MongoDB database instance

    Raises:
        Exception: If template parsing or insertion fails
    """
    collection = mongo_db["device_templates"]

    # Check if templates already seeded (idempotent)
    existing_count = collection.count_documents({})
    if existing_count > 0:
        logger.info(f"Device templates already seeded ({existing_count} documents found)")
        return

    logger.info("Seeding device templates into MongoDB...")

    inserted_count = 0
    for template_data in TEMPLATES_DATA:
        try:
            # Parse XML to JSON dict structure
            template_json = xml_to_json_dict(template_data["xml"])

            # Restore <ip> placeholder in the parsed dict
            import json
            json_str = json.dumps(template_json)
            json_str = json_str.replace("IP_PLACEHOLDER", "<ip>")
            template_json = json.loads(json_str)

            # Create MongoDB document
            doc = {
                "name": template_data["name"],
                "description": template_data["description"],
                "template": template_json,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            # Insert into collection
            result = collection.insert_one(doc)
            inserted_count += 1
            logger.debug(f"Inserted template '{template_data['name']}' with _id={result.inserted_id}")

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML for template '{template_data['name']}': {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to insert template '{template_data['name']}': {e}")
            raise

    logger.info(f"Successfully seeded {inserted_count} device templates into MongoDB")


__all__ = ["seed_device_templates", "xml_to_json_dict"]

