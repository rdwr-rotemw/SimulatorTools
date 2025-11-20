"""IRP helper utilities for IdsDataFormat conversion.

This module contains a placeholder conversion function that will be implemented
by the user to transform IdsDataFormat XML files into JSON-like Python dicts.
"""
from typing import Dict, Any, Optional
from typing import Tuple

from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator
from backend.app.modules.reporter.irp.core.irp_formatter import IrpFormatter


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
            out[str(msg_id)] = {
                "name": name,
                "data": _serialize_object(data)  # FIX: use _serialize_object, not str()
            }
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
            structs[name] = {
                "fields": _serialize_object(getattr(struct, "fields", None))  # FIX: use _serialize_object
            }
        except Exception:
            structs[name] = {"fields": None}

    namespaces_raw = getattr(templates_obj, "namespaces", None) or {}
    namespaces: Dict[str, Any] = {}
    for ns_name, ns_structs in namespaces_raw.items():
        try:
            namespaces[ns_name] = {
                k: _serialize_object(v) for k, v in ns_structs.items()  # FIX: use _serialize_object
            }
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
    """Recursively deserialize JSON back to ConvertXml objects."""
    if data is None:
        return None

    if isinstance(data, list):
        return [_deserialize_object(item) for item in data]

    if isinstance(data, dict):
        # Check if this is a serialized ConvertXml object
        if '__type__' in data and '__data__' in data:
            class_path = data['__type__']

            # Recursively deserialize nested data FIRST
            obj_data = {}
            for k, v in data['__data__'].items():
                obj_data[k] = _deserialize_object(v)

            # Now reconstruct the object
            if 'convert_xml.' in class_path:
                class_name = class_path.split('.')[-1]

                if hasattr(ConvertXml, class_name):
                    cls = getattr(ConvertXml, class_name)
                    try:
                        obj = object.__new__(cls)
                        obj.__dict__.update(obj_data)
                        return obj  # Return the actual ConvertXml object
                    except Exception as e:
                        print(f"ERROR: Failed to instantiate ConvertXml.{class_name}: {e}")
                        print(f"Class: {cls}, Data keys: {obj_data.keys()}")
                        raise
                else:
                    print(f"ERROR: ConvertXml.{class_name} not found!")
                    print(f"Available: {[x for x in dir(ConvertXml) if not x.startswith('_')]}")
                    raise AttributeError(f"ConvertXml.{class_name} not found")

            # Try regular class import
            try:
                parts = class_path.rsplit('.', 1)
                if len(parts) == 2:
                    module_path, class_name = parts
                    module = __import__(module_path, fromlist=[class_name])
                    cls = getattr(module, class_name)
                    obj = object.__new__(cls)
                    obj.__dict__.update(obj_data)
                    return obj
            except Exception as e:
                print(f"ERROR: Failed to deserialize {class_path}: {e}")
                raise

        # Regular dict - recursively deserialize values
        return {k: _deserialize_object(v) for k, v in data.items()}

    return data


# New helper: convert serialized dicts back into ConvertXml nested elements when needed
def _dict_to_convertxml_element(data_dict):
    """Convert a deserialized dict back to the proper ConvertXml class instance."""
    if not isinstance(data_dict, dict):
        return data_dict

    # Check if this has the object marker
    if '__type__' not in data_dict or '__data__' not in data_dict:
        # It's a plain dict (shouldn't happen after _deserialize_object, but handle it)
        return data_dict

    class_path = data_dict['__type__']
    obj_data = data_dict['__data__']

    # Extract class name
    if 'ConvertXml.' in class_path:
        class_name = class_path.split('.')[-1]
        if hasattr(ConvertXml, class_name):
            cls = getattr(ConvertXml, class_name)
            obj = object.__new__(cls)

            # Recursively convert nested dicts in obj_data
            for k, v in obj_data.items():
                if isinstance(v, list):
                    obj_data[k] = [_dict_to_convertxml_element(item) if isinstance(item, dict) else item for item in v]
                elif isinstance(v, dict) and '__type__' in v:
                    obj_data[k] = _dict_to_convertxml_element(v)

            obj.__dict__.update(obj_data)
            return obj

    return data_dict


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

    # DEBUG: Print raw message structure from MongoDB
    if 'schema' in doc and 'messages' in doc['schema']:
        messages_raw_from_mongo = doc['schema']['messages']
        print("DEBUG - Raw messages from MongoDB (first message):")
        first_msg_id = list(messages_raw_from_mongo.keys())[0]
        first_msg = messages_raw_from_mongo[first_msg_id]
        print(f"Message ID: {first_msg_id}")
        print(f"Keys: {first_msg.keys()}")
        print(f"Data type: {type(first_msg['data'])}")
        print(f"First data element: {first_msg['data'][0] if first_msg['data'] else 'empty'}")

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
    messages_raw = _deserialize_object(schema_blob.get('messages'))
    types = _deserialize_object(schema_blob.get('types'))
    templates = _deserialize_object(schema_blob.get('templates'))

    # Convert deserialized message dicts back to Message objects
    from backend.app.modules.reporter.irp.models.data_format_models import Message

    # Convert message dicts to Message objects with properly typed data
    messages = {}
    if messages_raw and isinstance(messages_raw, dict):
        for msg_id, msg_data in messages_raw.items():
            if isinstance(msg_data, dict) and 'name' in msg_data and 'data' in msg_data:
                # Ensure data elements are ConvertXml objects
                msg_data_list = msg_data['data']
                if isinstance(msg_data_list, list):
                    # Convert each element from dict to proper ConvertXml type
                    msg_data_typed = [_dict_to_convertxml_element(item) if isinstance(item, dict) else item                                        for item in msg_data_list]
                else:
                    msg_data_typed = msg_data_list

                messages[msg_id] = Message(msg_data['name'], msg_data_typed)
            else:
                messages[msg_id] = msg_data
    else:
        messages = messages_raw

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


def send_irp_message(schema_obj, message_id, message_data, from_ip: str, to_ip: str) -> Tuple[bool, str]:
    """Build and send a binary IRP message via UDP.

    Args:
        schema_obj: ConvertXml-like object with `schema` attribute
        message_id: ID of the message to build
        message_data: dict of values for the message fields
        from_ip: source IP address to bind from
        to_ip: destination IP address

    Returns:
        (True, "Sent") on success or (False, error_message)
    """
    try:
        # Use refactored IrpFormatter that accepts schema object
        formatter = IrpFormatter(schema_obj.schema, from_ip, to_ip)

        # Send message (internally uses MessageBuilder)
        formatter.send_message_from_data(message_id, message_data)

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
        tg = TemplateGenerator(schema_obj.schema)

        # Generate and return template (no file output)
        template = tg.generate_template(message_id, interactive=False)

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
