/**
 * Structure Parser Utility
 *
 * Converts MongoDB structure template format (_type, _properties, etc.)
 * into UI-friendly FieldValue format for form rendering.
 */

import { FieldValue, FieldType } from '../types/polling';

/**
 * Parse MongoDB structure template into FieldValue format.
 *
 * MongoDB format uses:
 * - _type: Field type (string, number, array, object, enum, timestamp, etc.)
 * - _properties: For objects, map of field names to their structures
 * - _item: For arrays, the structure of array items
 * - _options: For enums, list of allowed values
 * - _min, _max: For numbers and arrays, min/max constraints
 * - _offset: For timestamps, seconds offset from current time
 * - _required: Whether field is required
 *
 * UI format uses camelCase without underscores.
 *
 * @param mongoStructure - MongoDB structure template with _type, _properties, etc.
 * @returns Parsed FieldValue ready for form rendering
 */
export const parseStructureTemplate = (mongoStructure: any): FieldValue => {
  if (!mongoStructure) {
    return { type: FieldType.STRING };
  }

  const fieldType = mongoStructure._type;
  const parsed: FieldValue = {
    type: mapTypeToFieldType(fieldType),
  };

  // Handle OBJECT type - recursively parse properties
  if (fieldType === 'object' && mongoStructure._properties) {
    parsed.properties = {};
    Object.keys(mongoStructure._properties).forEach((key) => {
      parsed.properties![key] = parseStructureTemplate(mongoStructure._properties[key]);
    });
  }

  // Handle ARRAY type - parse item structure
  if (fieldType === 'array') {
    if (mongoStructure._item) {
      parsed.item = parseStructureTemplate(mongoStructure._item);
    }
    // Arrays don't have a 'value' - they have 'repeat' or 'repeat_min'/'repeat_max'
    // Initialize with repeat = 0 (user will configure)
    if (!parsed.repeat && !parsed.repeat_min) {
      parsed.repeat = 0;
    }
  }

  // Handle ENUM type - set options for dropdown
  if (fieldType === 'enum' && mongoStructure._options) {
    parsed.options = mongoStructure._options;
    // Set default value if provided
    if (mongoStructure._value !== undefined) {
      parsed.value = mongoStructure._value;
    }
  }

  // Handle NUMBER type - set min/max constraints
  if (fieldType === 'number') {
    if (mongoStructure._min !== undefined) {
      parsed.min = mongoStructure._min;
    }
    if (mongoStructure._max !== undefined) {
      parsed.max = mongoStructure._max;
    }
    // Set default value if provided
    if (mongoStructure._value !== undefined) {
      parsed.value = mongoStructure._value;
    }
  }

  // Handle STRING type - set default value if provided
  if (fieldType === 'string' && mongoStructure._value !== undefined) {
    parsed.value = mongoStructure._value;
  }

  // Handle TIMESTAMP type - extract offset
  if (fieldType === 'timestamp') {
    parsed.offset = mongoStructure._offset || 0;
  }


  return parsed;
};

/**
 * Map MongoDB type strings to FieldType enum.
 *
 * @param mongoType - Type string from MongoDB (_type field)
 * @returns Corresponding FieldType enum value
 */
const mapTypeToFieldType = (mongoType: string): FieldType => {
  const typeMap: Record<string, FieldType> = {
    string: FieldType.STRING,
    number: FieldType.NUMBER,
    boolean: FieldType.BOOLEAN,
    null: FieldType.NULL,
    object: FieldType.OBJECT,
    array: FieldType.ARRAY,
    ipv4: FieldType.RANDOM_IPV4,
    fqdn: FieldType.RANDOM_FQDN,
    timestamp: FieldType.TIMESTAMP,
    template: FieldType.TEMPLATE,
    enum: FieldType.STRING, // Enums are strings with options
    'attack-id': FieldType.STRING, // Special string type
  };

  return typeMap[mongoType] || FieldType.STRING;
};
