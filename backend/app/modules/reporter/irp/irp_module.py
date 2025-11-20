"""IRP helper utilities for IdsDataFormat conversion.

This module contains a placeholder conversion function that will be implemented
by the user to transform IdsDataFormat XML files into JSON-like Python dicts.
"""
from typing import Dict, Any, Optional
import importlib
from typing import Tuple

from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml
from backend.app.modules.reporter.irp.tools.message_builder import MessageBuilder
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator
from backend.app.modules.reporter.irp.tools.type_handler import TypeHandler
from backend.app.modules.reporter.irp.tools.footprint_template_generator import FootprintTemplateGenerator
import socket


def convert_xml(xml_file_path: str) -> Dict[str, Any]:
    """Convert IdsDataFormat XML file to complete JSON dict for storage.

    Args:
        xml_file_path: Path to downloaded XML file

    Returns:
        Dict containing complete parsed schema (messages, types, templates, namespaces)
    """
    try:
        # Create ConvertXml instance and parse
        converter = ConvertXml(xml_file_path)
        converter.convert_xml()

        if not getattr(converter, "schema", None):
            return {}

        schema = converter.schema

        # Serialize entire schema to dict
        schema_dict: Dict[str, Any] = {
            "messages": _serialize_messages(getattr(schema, "messages", None)),
            "types": _serialize_types(getattr(schema, "types", None)),
            "templates": _serialize_templates(getattr(schema, "templates", None)),
        }

        # Serialize any remaining ConvertXml objects recursively to JSON-compatible structures
        return _serialize_object(schema_dict)

    except Exception as e:
        raise RuntimeError(f"XML conversion error: {e}")


def _serialize_messages(messages: Optional[Dict[Any, Any]]) -> Dict[str, Any]:
    """Serialize messages to dict

    messages is expected to be a dict-like mapping of id -> message object
    where message has attributes `name` and `data`.
    """
    if not messages:
        return {}

    out: Dict[str, Any] = {}
    for msg_id, msg in messages.items():
        try:
            name = getattr(msg, "name", None)
            data = getattr(msg, "data", None)
            out[str(msg_id)] = {"name": name, "data": str(data)}
        except Exception:
            out[str(msg_id)] = {"name": None, "data": None}
    return out


def _serialize_types(types_obj: Optional[Any]) -> Dict[str, Any]:
    """Serialize types to dict

    Expected structure contains primitives, fixed_strings, ip_address, enums, bitmap, namespaces.
    """
    if not types_obj:
        return {}

    primitives = getattr(types_obj, "primitives", None) or {}
    fixed_strings = getattr(types_obj, "fixed_strings", None) or {}
    ip_addresses = getattr(types_obj, "ip_address", None) or {}

    enums_raw = getattr(types_obj, "enums", None) or {}
    enums: Dict[str, Any] = {}
    for name, enum in enums_raw.items():
        try:
            enums[name] = {"type": getattr(enum, "type", None), "values": getattr(enum, "values", None)}
        except Exception:
            enums[name] = {"type": None, "values": None}

    bitmap_obj = getattr(types_obj, "bitmap", None)
    bitmap = None
    if bitmap_obj:
        try:
            bitmap = {"type": getattr(bitmap_obj, "type", None), "values": getattr(bitmap_obj, "values", None)}
        except Exception:
            bitmap = None

    namespaces = getattr(types_obj, "namespaces", None) or {}

    return {
        "primitives": primitives,
        "fixed_strings": fixed_strings,
        "ip_addresses": ip_addresses,
        "enums": enums,
        "bitmap": bitmap,
        "namespaces": namespaces,
    }


def _serialize_templates(templates_obj: Optional[Any]) -> Dict[str, Any]:
    """Serialize templates to dict

    Expected structure: templates.structs and templates.namespaces
    """
    if not templates_obj:
        return {}

    structs_raw = getattr(templates_obj, "structs", None) or {}
    structs: Dict[str, Any] = {}
    for name, struct in structs_raw.items():
        try:
            structs[name] = {"fields": str(getattr(struct, "fields", None))}
        except Exception:
            structs[name] = {"fields": None}

    namespaces_raw = getattr(templates_obj, "namespaces", None) or {}
    namespaces: Dict[str, Any] = {}
    for ns_name, ns_structs in namespaces_raw.items():
        try:
            # ns_structs is expected to be a mapping
            namespaces[ns_name] = {k: str(v) for k, v in ns_structs.items()}
        except Exception:
            namespaces[ns_name] = {}

    return {"structs": structs, "namespaces": namespaces}


def _serialize_object(obj: Any) -> Any:
    """Recursively serialize ConvertXml objects to JSON-compatible dicts.

    Rules:
      - None -> None
      - list -> serialized list
      - dict -> serialized dict
      - objects with __dict__ -> dict of their attributes plus '__type__'
      - primitives returned as-is
    """
    # None
    if obj is None:
        return None

    # Lists
    if isinstance(obj, list):
        return [_serialize_object(item) for item in obj]

    # Dicts
    if isinstance(obj, dict):
        return {str(k): _serialize_object(v) for k, v in obj.items()}

    # Handle ConvertXml classes - store class name + attributes
    if hasattr(obj, '__class__') and getattr(obj.__class__, '__module__', '').startswith('backend.app.modules.reporter.irp'):
        data: Dict[str, Any] = {k: _serialize_object(v) for k, v in obj.__dict__.items()}
        return {
            '__type__': f"{obj.__class__.__module__}.{obj.__class__.__name__}",
            '__data__': data,
        }

    # Primitive types (str, int, float, bool, etc.)
    return obj


def _deserialize_object(data: Any) -> Any:
    """Recursively deserialize JSON back to ConvertXml objects"""
    if data is None:
        return None

    if isinstance(data, list):
        return [_deserialize_object(item) for item in data]

    if isinstance(data, dict):
        # Check if this is a serialized ConvertXml object
        if '__type__' in data and '__data__' in data:
            class_path = data['__type__']
            obj_data = {k: _deserialize_object(v) for k, v in data['__data__'].items()}

            # Attempt to import class
            try:
                module_path, class_name = class_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                obj = object.__new__(cls)
                # Update internal dict
                if isinstance(obj_data, dict):
                    obj.__dict__.update(obj_data)
                return obj
            except Exception:
                # Fallback: return raw dict
                return obj_data

        # Regular dict
        return {k: _deserialize_object(v) for k, v in data.items()}

    return data


def load_schema_from_mongo(mongo_db, document_id) -> Any:
    """Load a stored IdsDataFormat schema from MongoDB and reconstruct ConvertXml-like object.

    Args:
        mongo_db: pymongo database instance (from get_mongo_db())
        document_id: ObjectId or str representation of the Mongo document _id

    Returns:
        A ConvertXml-like object with `schema` attribute populated from stored data.
    """
    from bson.objectid import ObjectId

    # Accept string ids as well
    if not isinstance(document_id, ObjectId):
        try:
            document_id = ObjectId(document_id)
        except Exception as exc:
            raise ValueError(f"Invalid document_id: {exc}")

    doc = mongo_db.irp_data_formats.find_one({"_id": document_id})
    if not doc:
        raise KeyError(f"Document with id {document_id} not found in irp_data_formats")

    # Document may store schema at top-level keys or under a 'schema' field
    schema_blob = None
    if 'schema' in doc and isinstance(doc['schema'], dict):
        schema_blob = doc['schema']
    else:
        # Try to extract messages/types/templates at top-level
        if any(k in doc for k in ('messages', 'types', 'templates')):
            schema_blob = {
                'messages': doc.get('messages'),
                'types': doc.get('types'),
                'templates': doc.get('templates'),
            }

    if not schema_blob:
        raise KeyError("No serialized schema found in document")

    # Deserialize components
    messages = _deserialize_object(schema_blob.get('messages'))
    types = _deserialize_object(schema_blob.get('types'))
    templates = _deserialize_object(schema_blob.get('templates'))

    # Build a lightweight Schema object and attach to a ConvertXml-like wrapper
    Schema = type('Schema', (), {})
    schema_obj = Schema()
    setattr(schema_obj, 'messages', messages)
    setattr(schema_obj, 'types', types)
    setattr(schema_obj, 'templates', templates)

    # Create a ConvertXml-like instance without invoking __init__ (no file IO)
    try:
        cx = object.__new__(ConvertXml)
    except Exception:
        # Fallback to a generic container if ConvertXml cannot be instantiated this way
        cx = type('ConvertXmlLike', (), {})()

    setattr(cx, 'schema', schema_obj)
    # Keep minimal compatibility attributes
    setattr(cx, 'xml_file_path', None)
    setattr(cx, 'xml_dict', None)
    return cx


def send_irp_message(schema_obj, message_id, message_data, from_ip: str, to_ip: str, dest_port: int = 9000) -> Tuple[bool, str]:
    """Build and send a binary IRP message via UDP.

    Args:
        schema_obj: ConvertXml-like object with `schema` attribute
        message_id: ID of the message to build
        message_data: dict of values for the message fields
        from_ip: source IP address to bind from
        to_ip: destination IP address
        dest_port: destination UDP port (default 9000)

    Returns:
        (True, "Sent") on success or (False, error_message)
    """
    try:
        # Create a type handler and message builder
        type_handler = TypeHandler(getattr(schema_obj.schema, 'types', None))
        builder = MessageBuilder(schema_obj.schema, type_handler)

        # Build binary message
        msg_binary = builder.build_message(message_id, message_data)

        # Send via UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Bind to source IP (ephemeral port)
            sock.bind((from_ip, 0))
        except Exception:
            # If binding fails, continue without explicit source bind
            pass
        try:
            sock.sendto(msg_binary, (to_ip, int(dest_port)))
        finally:
            sock.close()

        return True, "Sent"
    except Exception as exc:
        return False, f"send_irp_message error: {exc!s}"


def create_irp_template(schema_obj, message_id) -> Dict[str, Any]:
    """Generate a template dict for a given message from a stored schema object.

    Args:
        schema_obj: ConvertXml-like object with `schema` attribute
        message_id: message ID to generate template for

    Returns:
        Template dict
    """
    try:
        # Create a TemplateGenerator-like instance without parsing a file
        tg = object.__new__(TemplateGenerator)
        # Assign schema and footprint generator used by TemplateGenerator methods
        setattr(tg, 'schema', getattr(schema_obj, 'schema', None))
        setattr(tg, 'footprint_generator', FootprintTemplateGenerator())

        template = TemplateGenerator.generate_template(tg, message_id)
        return template
    except Exception as exc:
        raise RuntimeError(f"create_irp_template error: {exc}")


def send_irp(mongo_id, message_id, message_data, from_ip: str, to_ip: str, mongo_db) -> Tuple[bool, str]:
    """Route wrapper: load schema from mongo and send an IRP message.

    Returns (True, 'Sent') or (False, error_message)
    """
    try:
        schema_obj = load_schema_from_mongo(mongo_db, mongo_id)
    except Exception as exc:
        return False, f"Failed to load schema: {exc!s}"

    ok, msg = send_irp_message(schema_obj, message_id, message_data, from_ip, to_ip)
    return ok, msg
