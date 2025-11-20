"""
Message Resolver: Utility for resolving message names to IDs from XML schemas.

This module provides functionality to resolve message identifiers, allowing users
to specify messages by either ID or name in JSON configuration files.
"""


class MessageResolver:
    """
    Resolves message names to IDs using the XML schema definition.
    """

    def __init__(self, schema):
        """
        Initialize the resolver with a parsed schema.

        Args:
            schema: Parsed XML schema containing message definitions
        """
        self.schema = schema
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """
        Build lookup tables for efficient message name/ID resolution.
        """
        self.name_to_id = {}
        self.id_to_name = {}

        if hasattr(self.schema, 'messages') and self.schema.messages:
            for message_id, message_obj in self.schema.messages.items():
                if hasattr(message_obj, 'name') and message_obj.name:
                    # Store both directions for lookup
                    self.name_to_id[message_obj.name] = message_id
                    self.id_to_name[message_id] = message_obj.name

    def resolve_message_identifier(self, identifier):
        """
        Resolve a message identifier (either ID or name) to a message ID.

        Args:
            identifier (str or int): Message ID or message name

        Returns:
            str: The message ID as a string

        Raises:
            ValueError: If the identifier cannot be resolved
        """
        # Handle numeric IDs (convert to string for consistency)
        if isinstance(identifier, int):
            identifier_str = str(identifier)
            if identifier_str in self.schema.messages:
                return identifier_str
            else:
                raise ValueError(f"Message ID {identifier} not found in schema")

        # Handle string inputs
        if isinstance(identifier, str):
            # First, try as direct ID lookup
            if identifier in self.schema.messages:
                return identifier

            # Then try as name lookup
            if identifier in self.name_to_id:
                return self.name_to_id[identifier]

            # Try parsing as numeric string
            try:
                numeric_id = int(identifier)
                return self.resolve_message_identifier(numeric_id)
            except ValueError:
                pass

            # If all else fails, provide helpful error message
            available_names = list(self.name_to_id.keys())[:5]  # Show first 5 for brevity
            available_ids = list(self.schema.messages.keys())[:5]
            raise ValueError(
                f"Message identifier '{identifier}' not found. "
                f"Available names: {available_names}... "
                f"Available IDs: {available_ids}..."
            )

        raise ValueError(f"Invalid message identifier type: {type(identifier)}")

    def get_message_name(self, message_id):
        """
        Get the message name for a given message ID.

        Args:
            message_id (str or int): Message ID

        Returns:
            str: The message name, or the ID if name not found
        """
        message_id_str = str(message_id)
        return self.id_to_name.get(message_id_str, message_id_str)

    def list_available_messages(self):
        """
        List all available messages with their IDs and names.

        Returns:
            list: List of dicts with 'id' and 'name' keys
        """
        messages = []
        for message_id, message_obj in self.schema.messages.items():
            messages.append({
                'id': message_id,
                'name': getattr(message_obj, 'name', f"message_{message_id}")
            })

        # Sort by numeric ID for better readability
        try:
            messages.sort(key=lambda x: int(x['id']))
        except ValueError:
            # If IDs aren't all numeric, sort alphabetically
            messages.sort(key=lambda x: x['id'])

        return messages

    def validate_message_exists(self, identifier):
        """
        Check if a message identifier exists without raising an exception.

        Args:
            identifier (str or int): Message ID or name

        Returns:
            bool: True if the message exists, False otherwise
        """
        try:
            self.resolve_message_identifier(identifier)
            return True
        except ValueError:
            return False
