"""
IrpFormatter: Schema-to-binary UDP message sender for IDS schemas.

Example usage:
    schema_obj = load_schema_from_mongo(mongo_db, mongo_id)
    irp = IrpFormatter(schema_obj.schema, "10.218.101.38", "172.17.40.1")
    irp.send_message(7, "message_values.json")
"""
import socket
import struct
import time

from backend.app.modules.reporter.irp.tools.type_handler import TypeHandler
from backend.app.modules.reporter.irp.tools.message_builder import MessageBuilder
from backend.app.modules.reporter.irp.tools.value_loader import ValueLoader
from backend.app.modules.reporter.irp.tools.message_resolver import MessageResolver
from backend.app.utils.logger import logger


class IrpFormatter:
    """
    Formats and sends messages as UDP packets using XML schema and JSON values.
    """

    def __init__(self, schema, from_ip, to_ip):
        self.from_ip = from_ip
        self.to_ip = to_ip
        self.schema = schema
        try:
            self.type_handler = TypeHandler(self.schema.types)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize type handler: {e}")
        try:
            self.message_builder = MessageBuilder(self.schema, self.type_handler)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize message builder: {e}")

        try:
            self.message_resolver = MessageResolver(self.schema)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize message resolver: {e}")
    def send_message(self, message_identifier, values_file, timeout=0):
        """
        Build and send a message by message ID or name using values from a JSON file.

        Args:
            message_identifier (str or int): Message ID (numeric) or message name
            values_file (str): Path to JSON values file
            timeout (int): Timeout in seconds for continuous sending (default: 0)
        """
        # Resolve message identifier to numeric ID
        try:
            message_id = self.message_resolver.resolve_message_identifier(message_identifier)
        except ValueError as e:
            raise ValueError(f"Message resolution failed: {e}")

        values = ValueLoader(values_file).values
        try:
            binary_data = self.message_builder.build_message(message_id, values)
        except Exception as e:
            message_name = self.message_resolver.get_message_name(message_id)
            raise RuntimeError(f"Failed to build message {message_id} ({message_name}): {e}")

        if timeout:
            start_time = time.time()
            while True:
                self._send_udp(binary_data, message_id)
                if time.time() - start_time >= timeout:
                    break
                time.sleep(15)
        else:
            self._send_udp(binary_data, message_id)

    def _send_udp(self, binary_data, message_id):
        version = 0x91
        event_type = 4
        timestamp = int(time.time())
        parser_version = 2
        byte_order = 1
        schema_version = 100600 if self.schema else 0
        # Ensure message_id is converted to integer for the UDP header
        code = int(message_id)
        data_header = struct.pack('<BBIBBIB', version, event_type, timestamp, parser_version, byte_order,
                                  schema_version, code)
        data = data_header + binary_data
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.from_ip, 0))
        except Exception as e:
            raise RuntimeError(f"Failed to bind UDP socket to {self.from_ip}: {e}")
        server_address = (self.to_ip, 2088)
        try:
            sock.sendto(data, server_address)
            logger.debug(f"IRP UDP sent from {self.from_ip} to {self.to_ip}:{server_address[1]}")
        except Exception as e:
            raise RuntimeError(f"Failed to send UDP data: {e}")
        finally:
            sock.close()

    def send_message_from_data(self, message_identifier, message_data):
        """
        Build and send a message by message ID or name using provided data dictionary.

        Args:
            message_identifier (str or int): Message ID (numeric) or message name
            message_data (dict): Message field values as dictionary
        """
        # Resolve message identifier to numeric ID
        try:
            message_id = self.message_resolver.resolve_message_identifier(message_identifier)
        except ValueError as e:
            raise ValueError(f"Message resolution failed: {e}")

        try:
            binary_data = self.message_builder.build_message(message_id, message_data)
        except Exception as e:
            message_name = self.message_resolver.get_message_name(message_id)
            raise RuntimeError(f"Failed to build message {message_id} ({message_name}): {e}")

        self._send_udp(binary_data, message_id)

    def list_available_messages(self):
        """
        List all available messages with their IDs and names.

        Returns:
            list: List of dicts with 'id' and 'name' keys
        """
        return self.message_resolver.list_available_messages()
