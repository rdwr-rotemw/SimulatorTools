"""Polling service for template management and XMF loading."""

from datetime import datetime, timezone
from typing import Tuple, List
from bson import ObjectId

from backend.app.models.polling import PollingTemplateCreate, EndpointConfig
from backend.app.modules.reporter.polling.xmf_generator import XMFGenerator
from backend.app.utils.auth import normalize_workspace_for_paths
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
            "endpoint": template.endpoint.model_dump(),
            "created_at": now,
            "updated_at": now,
        }

        result = collection.insert_one(doc)
        logger.info(f"Created polling template: {template.name} (ID: {result.inserted_id})")
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
        cursor = collection.find({}, {"endpoint": 0})

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
        endpoint_config = EndpointConfig(**doc["endpoint"])

        generator = XMFGenerator(endpoint_config)
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from template: {template_id}")
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
        workspace: str = "default"
    ) -> Tuple[bool, str]:
        """Write XMF content to filesystem via SSH.

        Args:
            xmf_content: Generated XMF TCL script
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            workspace: Workspace name

        Returns:
            (success, xmf_path or error_message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # Normalize workspace for file paths
            workspace = normalize_workspace_for_paths(workspace)

            # Determine XMF directory based on workspace
            if workspace == "default":
                xmf_dir = "/opt/sapro/xml/"
            else:
                xmf_dir = f"/opt/sapro/projects/{workspace}/xml/"

            # Ensure directory exists
            mkdir_cmd = f"mkdir -p {xmf_dir}"
            ssh_client.execute_command(mkdir_cmd)

            xmf_path = f"{xmf_dir}{xmf_filename}"

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

    def _create_device_map_xml(
        self,
        simulator_ip: str,
        xmf_filename: str
    ) -> str:
        """Create DeviceMap XML that references the XMF file.

        Args:
            simulator_ip: Simulator IP address
            xmf_filename: XMF filename (e.g., "50.50.180.1.xmf")

        Returns:
            DeviceMap XML string
        """
        return f'''<DeviceMap
    Release = "11.0"
    Description = ""
    UserData = ""
    SetupFile = ""
    Interface = ""
    Separator = ""
    StartInterfaceNum = "0"
    Username = "">
    <Device
        Name = "{simulator_ip}//161"
        Community = "public"
        Timeout = "3000"
        AuthPassword = ""
        PrivPassword = ""
        FileList = ""
        AgentFile = ""
        MibFile = "DefensePro_DP10_6_03.cmf"
        TelCmdFile = ""
        SoapFile = "{xmf_filename}"
        StartOnLoad = "No"
        Separator = ""
        Description = ""
        Location = ""
        Username = ""
        V1Enterprise = ""
        AuthUsername = ""
        PrivUsername = ""
        Context = ""
        MaxRepetitions = ""
        ActionFile = ""
        RemoteExtFile = ""
    />
</DeviceMap>'''

    async def load_xmf_to_simulator(
        self,
        simulator_ip: str,
        xmf_content: str,
        xmf_filename: str,
        map_name: str,
        workspace: str = "default"
    ) -> Tuple[bool, str]:
        """Load XMF onto simulator using update_device flow.

        Args:
            simulator_ip: Simulator IP address (for DeviceMap and routing)
            xmf_content: Generated XMF TCL script
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            map_name: Map name where simulator is located
            workspace: Workspace name

        Returns:
            (success, message)
        """
        # Step 1: Write XMF to filesystem
        success, xmf_path_or_error = self._write_xmf_to_filesystem(
            xmf_content, xmf_filename, workspace
        )

        if not success:
            return False, f"Failed to write XMF file: {xmf_path_or_error}"

        logger.info(f"XMF file written: {xmf_path_or_error}")

        # Step 2: Create DeviceMap XML referencing the XMF
        device_xml = self._create_device_map_xml(simulator_ip, xmf_filename)

        # Step 3: Call sapro_handler.update_device()
        try:
            success, message = self.sapro_handler.update_device(
                device_ip=simulator_ip,
                raw_xml_content=device_xml,
                map_name=map_name,
                workspace=workspace
            )

            if not success:
                return False, f"Failed to update device on Sapro: {message}"

            logger.info(f"Polling configuration loaded successfully for {simulator_ip} with XMF: {xmf_filename}")
            return True, f"Polling configuration loaded successfully for {simulator_ip}"

        except Exception as e:
            logger.error(f"Failed to update device: {e}", exc_info=True)
            return False, f"Failed to update device: {e}"
