"""Polling service for template management and XMF loading."""

from datetime import datetime, timezone
from typing import Tuple, List, Optional
from bson import ObjectId
import xml.etree.ElementTree as ET

from backend.app.models.polling import PollingTemplateCreate, EndpointConfig
from backend.app.modules.reporter.polling.xmf_generator import XMFGenerator
from backend.app.utils.logger import logger
from backend.app.utils.sapro_ssh import get_sapro_ssh_client


class PollingService:
    """Service for polling template management and XMF operations."""

    def __init__(self, mongo_db, sapro_handler):
        """Initialize polling service.

        Args:
            mongo_db: MongoDB database instance
            sapro_handler: Sapro communication handler instance
        """
        self.mongo_db = mongo_db
        self.sapro_handler = sapro_handler

    async def create_template(self, template: PollingTemplateCreate) -> str:
        """Save template to MongoDB.

        Args:
            template: Template creation request

        Returns:
            MongoDB ObjectId as string

        Raises:
            ValueError: If template name already exists
        """
        collection = self.mongo_db["polling_templates"]

        # Check unique name
        existing = collection.find_one({"name": template.name})
        if existing:
            raise ValueError(f"Template name '{template.name}' already exists")

        now = datetime.now(timezone.utc)
        doc = {
            "name": template.name,
            "description": template.description,
            "endpoints": [endpoint.model_dump() for endpoint in template.endpoints],
            "created_at": now,
            "updated_at": now,
        }

        result = collection.insert_one(doc)
        logger.info(f"Created polling template: {template.name} with {len(template.endpoints)} endpoint(s) (ID: {result.inserted_id})")
        return str(result.inserted_id)

    async def get_template(self, template_id: str) -> dict:
        """Retrieve template from MongoDB.

        Args:
            template_id: MongoDB ObjectId as string

        Returns:
            Template document

        Raises:
            ValueError: If template not found
        """
        collection = self.mongo_db["polling_templates"]
        oid = ObjectId(template_id)
        doc = collection.find_one({"_id": oid})

        if not doc:
            raise ValueError(f"Template not found: {template_id}")

        return doc

    async def list_templates(self) -> list:
        """List all templates (lightweight - no full config).

        Returns:
            List of template summaries
        """
        collection = self.mongo_db["polling_templates"]
        cursor = collection.find({}, {"endpoints": 0})

        result = []
        for doc in cursor:
            result.append({
                "_id": str(doc["_id"]),
                "name": doc["name"],
                "description": doc.get("description"),
                "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None
            })

        return result

    async def delete_template(self, template_id: str) -> bool:
        """Delete template from MongoDB.

        Args:
            template_id: MongoDB ObjectId as string

        Returns:
            True if deleted, False if not found
        """
        collection = self.mongo_db["polling_templates"]
        oid = ObjectId(template_id)

        result = collection.delete_one({"_id": oid})

        if result.deleted_count > 0:
            logger.info(f"Deleted polling template: {template_id}")
            return True
        return False

    async def generate_xmf_from_template(
        self,
        template_id: str
    ) -> str:
        """Generate XMF content from saved template.

        NOTE: No simulator IP/version needed - they're generated in TCL!

        Args:
            template_id: MongoDB template ID

        Returns:
            Generated XMF TCL script
        """
        doc = await self.get_template(template_id)
        endpoints = [EndpointConfig(**ep) for ep in doc["endpoints"]]

        generator = XMFGenerator(endpoints)
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from template: {template_id} with {len(endpoints)} endpoint(s)")
        return xmf_content

    async def generate_xmf_from_config(
        self,
        endpoint_config: EndpointConfig
    ) -> str:
        """Generate XMF content from single endpoint config (backward compatibility).

        NOTE: No simulator IP/version needed - they're generated in TCL!

        Args:
            endpoint_config: Single endpoint configuration

        Returns:
            Generated XMF TCL script
        """
        # Wrap single endpoint in list for new generator
        generator = XMFGenerator([endpoint_config])
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from config: {endpoint_config.path}")
        return xmf_content

    async def generate_xmf_from_endpoints(
        self,
        endpoints: List[EndpointConfig]
    ) -> str:
        """Generate XMF content from multiple endpoint configs.

        NOTE: No simulator IP/version needed - they're generated in TCL!

        Args:
            endpoints: List of endpoint configurations

        Returns:
            Generated XMF TCL script with all endpoints
        """
        if not endpoints or len(endpoints) == 0:
            raise ValueError("At least one endpoint required")

        generator = XMFGenerator(endpoints)
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from {len(endpoints)} endpoint(s)")
        return xmf_content

    def _write_xmf_to_filesystem(
        self,
        xmf_content: str,
        xmf_filename: str,
        workspace: str,
        overwrite: bool = False
    ) -> Tuple[bool, str]:
        """Write XMF content to filesystem via SSH.

        Args:
            xmf_content: Generated XMF TCL script
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            workspace: Workspace name
            overwrite: Whether to overwrite if file exists (default: False)

        Returns:
            (success, xmf_path or error_message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # Determine XMF directory based on workspace
            if workspace == "default" or workspace == "*":
                xmf_dir = "/opt/sapro/xml/"
            else:
                xmf_dir = f"/opt/sapro/projects/{workspace}/xml/"

            # Ensure directory exists
            mkdir_cmd = f"mkdir -p {xmf_dir}"
            ssh_client.execute_command(mkdir_cmd)

            xmf_path = f"{xmf_dir}{xmf_filename}"

            # Check if file exists (unless overwrite is True)
            if not overwrite:
                check_cmd = f"test -f {xmf_path} && echo 'exists' || echo 'not_exists'"
                success, output = ssh_client.execute_command(check_cmd)
                if success and output.strip() == 'exists':
                    return False, f"FILE_EXISTS:{xmf_path}"

            # Escape content for shell
            escaped_content = xmf_content.replace("'", "'\\''")
            write_cmd = f"echo '{escaped_content}' > {xmf_path}"

            success, output = ssh_client.execute_command(write_cmd)

            if not success:
                return False, f"Failed to write XMF file: {output}"

            logger.info(f"XMF file written to: {xmf_path}")
            return True, xmf_path

        except Exception as e:
            logger.error(f"Failed to write XMF to filesystem: {e}", exc_info=True)
            return False, str(e)

    def _get_device_config_from_map(
        self,
        device_ip: str,
        map_path: str
    ) -> Optional[ET.Element]:
        """Get device configuration from map file via SSH.

        Args:
            device_ip: Device IP address to find
            map_path: Full path to map file

        Returns:
            Device XML element if found, None otherwise
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # Read map file content via SSH
            read_cmd = f"cat {map_path}"
            success, output = ssh_client.execute_command(read_cmd)

            if not success:
                logger.error(f"Failed to read map file {map_path}: {output}")
                return None

            # Parse XML
            try:
                root = ET.fromstring(output)
            except ET.ParseError as e:
                logger.error(f"Failed to parse map XML from {map_path}: {e}")
                return None

            # Find device by IP (check both Name attribute and Name with port suffix)
            for device in root.findall('.//Device'):
                general = device.find('General')
                if general is not None:
                    name = general.get('Name', '')
                    # Match exact IP or IP with port (e.g., "50.50.135.4" or "50.50.135.4//161")
                    if name == device_ip:
                        logger.info(f"Found device {device_ip} in map {map_path}")
                        return device

            logger.warning(f"Device {device_ip} not found in map {map_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to get device config from map: {e}", exc_info=True)
            return None

    def _format_element_with_attributes(self, element: ET.Element, indent_level: int) -> str:
        """Format an XML element with attributes on separate lines (Sapro style).

        Args:
            element: XML element to format
            indent_level: Current indentation level (number of tabs)

        Returns:
            Formatted XML string
        """
        indent = '\t' * indent_level
        attr_indent = '\t' * (indent_level + 1)

        # Get element tag and attributes
        tag = element.tag
        attrs = element.attrib

        # Start building the element
        if attrs:
            # Opening tag with attributes on separate lines
            lines = [f'{indent}<{tag}']
            for key, value in attrs.items():
                lines.append(f'{attr_indent}{key} = "{value}"')

            # Check if element has children
            if len(element) > 0:
                # Has children - close tag and process children
                lines.append(f'{indent}/>')
                result = '\n'.join(lines)

                # Process children recursively
                for child in element:
                    result += '\n' + self._format_element_with_attributes(child, indent_level + 1)

                return result
            else:
                # No children - self-closing tag
                lines[-1] = lines[-1]  # Keep last attribute line as is
                lines.append(f'{indent}/>')
                return '\n'.join(lines)
        else:
            # No attributes - simple tag
            if len(element) > 0:
                result = f'{indent}<{tag}>'
                for child in element:
                    result += '\n' + self._format_element_with_attributes(child, indent_level + 1)
                result += f'\n{indent}</{tag}>'
                return result
            else:
                return f'{indent}<{tag}/>'

    def _update_device_soap_file(
        self,
        device_element: ET.Element,
        xmf_filepath: str
    ) -> str:
        """Update SoapModFile in device XML element and wrap in DeviceMap.

        Args:
            device_element: Device XML element
            xmf_filepath: Full path to XMF file on Sapro server

        Returns:
            Complete DeviceMap XML string with updated device (properly formatted for Sapro)
        """
        # Find and update Soap/SoapModFile
        soap = device_element.find('Soap')
        if soap is not None:
            soap.set('SoapModFile', xmf_filepath)
            logger.info(f"Updated SoapModFile to: {xmf_filepath}")
        else:
            logger.warning("Soap element not found in device config")

        # Format device element with proper Sapro formatting
        device_xml_formatted = self._format_element_with_attributes(device_element, 1)

        # Wrap in DeviceMap structure with proper Sapro formatting
        device_map_xml = f'''<DeviceMap
\tRelease = "11.0"
\tDescription = ""
\tUserData = ""
\tSetupFile = ""
\tInterface = ""
\tSeparator = ""
\tStartInterfaceNum = "0"
\tUsername = "">
{device_xml_formatted}
</DeviceMap>'''

        return device_map_xml

    async def load_xmf_to_simulator(
        self,
        device_ip: str,
        xmf_content: str,
        xmf_filename: str,
        map_path: str,
        workspace: str,
        overwrite: bool = False,
        write_xmf: bool = True
    ) -> Tuple[bool, str]:
        """Load XMF onto simulator by updating device's SoapModFile.

        This function:
        1. Optionally writes XMF to filesystem (if write_xmf=True)
        2. Reads current device configuration from map file
        3. Updates only the SoapModFile field with new XMF path
        4. Updates device using update_device()

        Args:
            device_ip: Device IP address
            xmf_content: Generated XMF TCL script (can be empty if write_xmf=False)
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            map_path: Full path to map file (e.g., /opt/sapro/map/default.map)
            workspace: Workspace name (for XMF file path determination)
            overwrite: Whether to overwrite existing XMF file (default: False)
            write_xmf: Whether to write XMF file (default: True). Set to False when XMF already written.

        Returns:
            (success, message)
        """
        # Extract map_name for logging
        map_name = map_path.split('/')[-1].replace('.map', '')

        logger.info(f"Loading XMF for device {device_ip} in map '{map_name}'")

        # Step 2: Optionally write XMF to filesystem
        if write_xmf:
            success, xmf_path_or_error = self._write_xmf_to_filesystem(
                xmf_content, xmf_filename, workspace, overwrite=overwrite
            )

            if not success:
                return False, xmf_path_or_error

            xmf_full_path = xmf_path_or_error
            logger.info(f"XMF file written: {xmf_full_path}")
        else:
            # XMF already written, just construct the path
            if workspace == "default" or workspace == "*":
                xmf_dir = "/opt/sapro/xml/"
            else:
                xmf_dir = f"/opt/sapro/projects/{workspace}/xml/"
            xmf_full_path = f"{xmf_dir}{xmf_filename}"
            logger.info(f"Using existing XMF file: {xmf_full_path}")

        # Step 3: Get current device configuration from map
        device_element = self._get_device_config_from_map(
            device_ip=device_ip,
            map_path=map_path
        )

        if device_element is None:
            return False, f"Device {device_ip} not found in map file '{map_name}'"

        # Step 4: Update only SoapModFile
        logger.info(f"Updating SoapModFile for device {device_ip}")
        device_xml = self._update_device_soap_file(device_element, xmf_full_path)

        # Step 5: Call sapro_handler.update_device()
        try:
            success, message = self.sapro_handler.update_device(
                device_ip=device_ip,
                raw_xml_content=device_xml,
                map_path=map_path
            )

            if not success:
                return False, f"Failed to update device on Sapro: {message}"

            logger.info(f"Polling configuration loaded successfully for {device_ip} with XMF: {xmf_filename}")
            return True, f"Polling configuration loaded successfully for {device_ip}"

        except Exception as e:
            logger.error(f"Failed to update device: {e}", exc_info=True)
            return False, f"Failed to update device: {e}"
