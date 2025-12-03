from typing import Dict, Any, Optional, Union
from typing import Tuple

from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml
from backend.app.modules.reporter.irp.tools.message_resolver import MessageResolver
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
    """Serialize types to dict"""
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
            bitmap = {"name": getattr(bitmap_obj, "name"), "type": getattr(bitmap_obj, "type", None),
                      "values": getattr(bitmap_obj, "values", None)}
        except Exception:
            bitmap = None

    # Properly serialize namespaces with _serialize_object
    namespaces_raw = getattr(types_obj, "namespaces", None) or {}
    namespaces: Dict[str, Any] = {}
    for ns_name, ns_dict in namespaces_raw.items():
        try:
            serialized_ns: Dict[str, Any] = {}
            for key, value in ns_dict.items():
                serialized_ns[key] = _serialize_object(value)
            namespaces[ns_name] = serialized_ns
        except Exception:
            namespaces[ns_name] = {}

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
                "fields": _serialize_object(getattr(struct, "fields", None))
            }
        except Exception:
            structs[name] = {"fields": None}

    namespaces_raw = getattr(templates_obj, "namespaces", None) or {}
    namespaces: Dict[str, Any] = {}
    for ns_name, ns_obj in namespaces_raw.items():
        try:
            # ns_obj is a Namespace object with .structs attribute
            ns_structs_dict = getattr(ns_obj, 'structs', None) or {}
            namespaces[ns_name] = {
                struct_name: _serialize_object(struct_obj)
                for struct_name, struct_obj in ns_structs_dict.items()
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
    if hasattr(obj, '__class__') and getattr(obj.__class__, '__module__', '').startswith(
            'backend.app.modules.reporter.irp'):
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
            # If the serialized type points to convert_xml module (e.g. backend.app.modules.reporter.irp.tools.convert_xml.DataField)
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


# New helper: reconstruct a Templates object (with Struct and Namespace instances)
# from a deserialized templates dict or Templates-like object
def _reconstruct_templates_object(templates_dict):
    """Reconstruct a Templates instance (Templates.structs, Templates.namespaces)

    Accepts either a plain dict (as produced by serialization) or an already
    deserialized object with attributes 'structs' and 'namespaces' that may
    contain plain dicts. Returns a Templates instance populated with Struct
    and Namespace objects where each Struct.data is a list of properly-typed
    ConvertXml elements.
    """
    from backend.app.modules.reporter.irp.models.data_format_models import Templates, Struct, Namespace

    templates = Templates()
    if not templates_dict:
        return templates

    # Helper to obtain 'fields' list from either a dict or an object
    def _get_fields(sdata):
        if isinstance(sdata, dict):
            return sdata.get('fields')
        return getattr(sdata, 'fields', None)

    # Extract raw structs and namespaces whether input is dict or object
    if isinstance(templates_dict, dict):
        structs_raw = templates_dict.get('structs') or {}
        namespaces_raw = templates_dict.get('namespaces') or {}
    else:
        structs_raw = getattr(templates_dict, 'structs', {}) or {}
        namespaces_raw = getattr(templates_dict, 'namespaces', {}) or {}

    # Reconstruct structs
    structs_out = {}
    if isinstance(structs_raw, dict):
        for struct_name, struct_data in structs_raw.items():
            fields = _get_fields(struct_data)
            if isinstance(fields, list):
                converted_fields = [_dict_to_convertxml_element(f) if isinstance(f, dict) else f for f in fields]
            else:
                converted_fields = fields
            s = Struct(struct_name, converted_fields)
            # Provide both 'data' and 'fields' attributes for compatibility
            setattr(s, 'data', converted_fields)
            setattr(s, 'fields', converted_fields)
            structs_out[struct_name] = s

    templates.set_structs(structs_out)

    # Reconstruct namespaces
    namespaces_out = {}
    if isinstance(namespaces_raw, dict):
        for ns_name, ns_structs in namespaces_raw.items():
            ns_structs_out = {}
            if isinstance(ns_structs, dict):
                for sname, sdata in ns_structs.items():
                    # Obtain fields and data from either dict or object form
                    fields = _get_fields(sdata)
                    if isinstance(fields, list):
                        converted_fields = [_dict_to_convertxml_element(f) if isinstance(f, dict) else f for f in
                                            fields]
                    else:
                        converted_fields = fields

                    # Also check for 'data' attribute which may contain template elements
                    if isinstance(sdata, dict):
                        raw_data = sdata.get('data')
                    else:
                        raw_data = getattr(sdata, 'data', None)

                    if isinstance(raw_data, list):
                        converted_data = [_dict_to_convertxml_element(item) if isinstance(item, dict) else item for item
                                          in raw_data]
                    else:
                        converted_data = raw_data

                    # Prefer converted_data for the Struct.body if present, otherwise use converted_fields
                    struct_body = converted_data if isinstance(converted_data, list) else converted_fields

                    s = Struct(sname, struct_body)
                    # Ensure both attributes are available for TemplateGenerator compatibility
                    setattr(s, 'data', converted_data if converted_data is not None else converted_fields)
                    setattr(s, 'fields', converted_fields if converted_fields is not None else converted_data)
                    ns_structs_out[sname] = s
            namespaces_out[ns_name] = Namespace(ns_name, ns_structs_out)

    templates.set_namespaces(namespaces_out)
    return templates


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
    if 'xml_schema' in doc and isinstance(doc['xml_schema'], dict):
        schema_blob = doc['xml_schema']
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
    types_raw = _deserialize_object(schema_blob.get('types'))
    templates_raw = _deserialize_object(schema_blob.get('templates'))

    # DEBUG: Check what's in templates_raw before reconstruction
    if templates_raw and isinstance(templates_raw, dict):
        if 'namespaces' in templates_raw and 'trafmon' in templates_raw['namespaces']:
            trafmon_ns = templates_raw['namespaces']['trafmon']
            print(f"DEBUG load_schema: trafmon namespace in raw deserialized data (templates):")
            print(f"  - Type: {type(trafmon_ns)}")
            print(f"  - Keys/attrs: {list(trafmon_ns.keys()) if isinstance(trafmon_ns, dict) else dir(trafmon_ns)}")
            if isinstance(trafmon_ns, dict):
                print(f"  - Content: {list(trafmon_ns.items())[:5]}")

    # DEBUG: Check types namespaces too
    if types_raw and isinstance(types_raw, dict):
        if 'namespaces' in types_raw:
            print(f"DEBUG load_schema: types.namespaces keys: {list(types_raw['namespaces'].keys())}")
            if 'trafmon' in types_raw['namespaces']:
                trafmon_types = types_raw['namespaces']['trafmon']
                print(f"DEBUG load_schema: trafmon in types.namespaces:")
                print(f"  - Type: {type(trafmon_types)}")
                print(f"  - Keys: {list(trafmon_types.keys()) if isinstance(trafmon_types, dict) else 'not a dict'}")
                if isinstance(trafmon_types, dict):
                    print(f"  - Content (first 5 items): {list(trafmon_types.items())[:5]}")
            else:
                print(f"DEBUG load_schema: trafmon NOT in types.namespaces")
        else:
            print(f"DEBUG load_schema: types has no 'namespaces' key")
    else:
        print(f"DEBUG load_schema: types_raw is None or not a dict")

    # Reconstruct templates into a proper Templates object with Struct/Namespace instances
    templates = _reconstruct_templates_object(templates_raw)

    # DEBUG: Check after reconstruction
    if templates and hasattr(templates, 'namespaces'):
        trafmon_ns_after = templates.namespaces.get('trafmon')
        if trafmon_ns_after:
            print(f"DEBUG load_schema: trafmon namespace AFTER reconstruction:")
            print(f"  - Type: {type(trafmon_ns_after)}")
            print(f"  - Has structs: {hasattr(trafmon_ns_after, 'structs')}")
            if hasattr(trafmon_ns_after, 'structs'):
                print(f"  - Structs: {list(trafmon_ns_after.structs.keys()) if trafmon_ns_after.structs else 'empty'}")

    # Convert template structs to have properly typed fields
    if templates and hasattr(templates, 'structs'):
        structs = getattr(templates, 'structs') or {}
        if isinstance(structs, dict):
            for struct_name, struct_obj in structs.items():
                if hasattr(struct_obj, 'fields'):
                    fields = getattr(struct_obj, 'fields')
                    if isinstance(fields, list):
                        struct_obj.fields = [_dict_to_convertxml_element(field) if isinstance(field, dict) else field
                                             for field in fields]
                    else:
                        setattr(struct_obj, 'fields', fields)

    # Convert deserialized message dicts back to Message objects
    from backend.app.modules.reporter.irp.models.data_format_models import Message

    # Convert message dicts to Message objects with properly typed data
    messages = {}
    if messages_raw and isinstance(messages_raw, dict):
        for msg_id, msg_data in messages_raw.items():
            if isinstance(msg_data, dict) and 'name' in msg_data and 'data' in msg_data:
                msg_data_list = msg_data['data']
                if isinstance(msg_data_list, list):
                    msg_data_typed = [_dict_to_convertxml_element(item) if isinstance(item, dict) else item
                                      for item in msg_data_list]
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

    # Ensure types is a proper Types() object (not just a dict) before attaching
    from backend.app.modules.reporter.irp.models.data_format_models import Types

    types_obj = None
    try:
        # If already an instance of Types, use it directly
        if isinstance(types_raw, Types):
            types_obj = types_raw
        else:
            # Construct a Types instance and populate fields from the deserialized dict if available
            types_obj = Types()
            if isinstance(types_raw, dict):
                types_obj.set_primitives(types_raw.get('primitives') or {})
                types_obj.set_fixed_strings(types_raw.get('fixed_strings') or {})
                # Support either 'ip_addresses' or 'ip_address' keys
                types_obj.set_ip_address(types_raw.get('ip_addresses') or types_raw.get('ip_address') or {})
                types_obj.set_enums(types_raw.get('enums') or {})
                types_obj.set_bitmap(types_raw.get('bitmap'))
                types_obj.set_namespaces(types_raw.get('namespaces') or {})
            else:
                # Unknown shape: attach as-is to preserve data
                types_obj = types_raw
    except Exception:
        # On any error, fall back to the raw deserialized value
        types_obj = types_raw

    setattr(schema_obj, 'types', types_obj)
    setattr(schema_obj, 'templates', templates)

    # Create a ConvertXml-like instance without invoking __init__ (no file IO)
    try:
        cx = object.__new__(ConvertXml)
    except Exception:
        cx = type('ConvertXmlLike', (), {})()

    setattr(cx, 'schema', schema_obj)
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


def create_irp_template(schema_obj, message_identifier) -> Dict[str, Any]:
    """Generate a template dict for a given message from a stored schema object.

    Args:
        schema_obj: ConvertXml-like object with `schema` attribute
        message_identifier: message ID (int/str) or message name to generate template for

    Returns:
        Dict with 'success', 'name', and 'template' keys
    """
    try:
        # Resolve message identifier (handles both ID and name)
        message_resolver = MessageResolver(schema_obj.schema)
        message_id = int(message_resolver.resolve_message_identifier(message_identifier))
        message_name = message_resolver.get_message_name(message_id)

        tg = TemplateGenerator(schema_obj.schema)

        # Generate template (no file output)
        template = tg.generate_template(message_id, interactive=False)

        return {
            "success": True,
            "name": message_name,
            "template": template
        }
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise


def send_irp_messages(schema_obj, message_data, from_ip: str, to_ip: str) -> Union[
    Dict[str, Tuple[bool, str]], Tuple[bool, str]]:
    """Build and send a binary IRP message via UDP.

    Args:
        schema_obj: ConvertXml-like object with `schema` attribute
        message_data: dict of values for the message fields
        from_ip: source IP address to bind from
        to_ip: destination IP address

    Returns:
        (True, "Sent") on success or (False, error_message)
    """
    results = {}
    try:
        for message in message_data['messages']:
            name = message['message']
            del message['message']
            ok, msg = send_irp_message(schema_obj, name, message, from_ip, to_ip)
            results[name] = ok, msg
        return results
    except Exception as exc:
        return False, f"send_irp_message error: {exc!s}"
