/**
 * TypeScript types for Polling API integration.
 *
 * Matches backend Pydantic models from backend/app/models/polling.py
 * Provides type-safe interfaces for polling template management and XMF generation.
 */

/**
 * Enum for all supported field types in polling data structure.
 *
 * Static types: STRING, NUMBER, BOOLEAN, NULL
 * Dynamic types: TIMESTAMP, RANDOM, RANDOM_IPV4, RANDOM_FQDN, RANDOM_COMPOSITE, TEMPLATE
 * Container types: OBJECT, ARRAY
 */
export enum FieldType {
  // Static types
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  NULL = 'null',

  // Dynamic types
  TIMESTAMP = 'timestamp',
  RANDOM = 'random',
  RANDOM_IPV4 = 'random_ipv4',
  RANDOM_FQDN = 'random_fqdn',
  RANDOM_COMPOSITE = 'random_composite',
  TEMPLATE = 'template',

  // Container types
  OBJECT = 'object',
  ARRAY = 'array',
}

/**
 * Part of a random composite value (for building composite values like attack IDs).
 */
export interface RandomCompositePart {
  type: 'random' | 'literal';
  min?: number;
  max?: number;
  value?: string;
}

/**
 * Recursive field value configuration.
 * Represents a single field in the user's data structure with all possible configurations.
 *
 * - For static values (STRING, NUMBER, BOOLEAN, NULL): use 'value' field
 * - For random numbers (RANDOM): use 'min' and 'max'
 * - For random FQDN (RANDOM_FQDN): use 'suffix'
 * - For random composite (RANDOM_COMPOSITE): use 'parts' array
 * - For timestamp (TIMESTAMP): use 'offset' (seconds from current time)
 * - For template substitution (TEMPLATE): use 'value' with {{INDEX}} placeholder
 * - For object (OBJECT): use 'properties' map
 * - For array (ARRAY): use 'repeat' or 'repeat_min'/'repeat_max', and 'item'
 */
export interface FieldValue {
  type: FieldType;

  // For fields that support random/fixed modes
  mode?: 'random' | 'fixed'; // User chooses random or fixed

  // For static values (STRING, NUMBER, BOOLEAN, NULL)
  value?: string | number | boolean | null;

  // For random numbers (RANDOM)
  min?: number;
  max?: number;

  // For random FQDN (RANDOM_FQDN)
  suffix?: string;

  // For random composite (RANDOM_COMPOSITE)
  parts?: RandomCompositePart[];

  // For timestamp (TIMESTAMP) - offset in seconds from current time
  offset?: number;

  // For object (OBJECT) - nested fields
  properties?: Record<string, FieldValue>;

  // For array (ARRAY)
  repeat?: number; // Fixed count
  repeat_min?: number; // Min count for random
  repeat_max?: number; // Max count for random
  item?: FieldValue; // Array item structure (object or primitive)

  // Enum options (for dropdown fields like tcp-flag, protocol)
  options?: string[];
}

/**
 * Endpoint configuration - user configures only this part.
 *
 * The simulator uses this to:
 * - Respond at the specified endpoint path
 * - Use the polling intervals for XMF generation
 * - Build the user-defined data structure in responses
 */
export interface EndpointConfig {
  path: string; // e.g., '/v1/attack-data'
  method?: string; // default 'GET'
  data_key: string; // Main data key name in response (e.g., 'attack_data')
  polling_interval_seconds?: number; // default 60
  data_structure: Record<string, FieldValue>; // User-defined structure
}

/**
 * Full polling template with metadata and endpoint config.
 */
export interface PollingTemplate {
  _id: string; // MongoDB ObjectId as string
  name: string;
  description: string;
  created_at: string; // ISO format datetime
  endpoint: EndpointConfig;
}

/**
 * Lightweight template summary (without full config).
 * Used for list operations.
 */
export interface PollingTemplateSummary {
  _id: string;
  name: string;
  description?: string;
  created_at?: string;
}

/**
 * Request payload for creating a new polling template.
 */
export interface PollingTemplateCreate {
  name: string;
  description: string;
  endpoint: EndpointConfig;
}

/**
 * Payload for polling configuration endpoints.
 *
 * User provides either:
 * - template_id: to load and use a saved template
 * - endpoint_config: to generate on-the-fly without saving
 *
 * Always required:
 * - xmf_filename: user-provided XMF filename (e.g., 'attack_data.xmf')
 */
export interface PollingPayload {
  template_id?: string; // Load from saved template
  endpoint_config?: EndpointConfig; // Or generate on-the-fly
  xmf_filename: string; // User-provided filename (required)
}

/**
 * Generic polling API response.
 */
export interface PollingResponse {
  success: boolean;
  message: string;
}

/**
 * Response from list templates endpoint.
 */
export interface TemplateListResponse {
  success: boolean;
  templates: PollingTemplateSummary[];
}

/**
 * Response from get template detail endpoint.
 */
export interface TemplateDetailResponse {
  success: boolean;
  template: PollingTemplate;
}

/**
 * Response from create template endpoint.
 */
export interface TemplateCreateResponse {
  success: boolean;
  template_id: string; // MongoDB ObjectId as string
  message: string;
}

/**
 * Data key option for UI dropdown/selector.
 * Maps user-facing labels to technical values and documentation.
 */
export interface DataKeyOption {
  value: string; // e.g., 'attack_data'
  label: string; // e.g., 'Attack Data'
  endpoint: string; // e.g., '/v1/attack-data'
  description: string; // e.g., 'DNS-Protection and Behavioral-DoS attack data'
}

/**
 * Pre-configured data key options matching DefensePro API endpoints.
 */
export const DATA_KEY_OPTIONS: DataKeyOption[] = [
  {
    value: 'attack_data',
    label: 'Attack Data',
    endpoint: '/v1/attack-data',
    description: 'DNS-Protection and Behavioral-DoS attack data',
  },
  {
    value: 'application_traffic_v1',
    label: 'Application Traffic (v1)',
    endpoint: '/v1/traffic/application',
    description: 'TLS-Fingerprint application data - array structure',
  },
  {
    value: 'application_traffic_v2',
    label: 'Application Traffic (v2)',
    endpoint: '/v2/traffic/application',
    description: 'TLS-Fingerprint and DNS-Protection - nested object with categories',
  },
  {
    value: 'policy_traffic',
    label: 'Policy Traffic',
    endpoint: '/v1/traffic/policy',
    description: 'Policy-based traffic statistics',
  },
  {
    value: 'application_characteristics',
    label: 'Application Characteristics (Web DDoS Baseline)',
    endpoint: '/v1/traffic/application/characteristics',
    description: 'Web DDoS baseline and TLS fingerprint characteristics',
  },
];

/**
 * Helper type for UI field configuration.
 * Used to track field hierarchy and nesting in the UI builder.
 */
export interface FieldConfig {
  id: string; // Unique field identifier in the UI
  name: string; // Field name
  value: FieldValue; // Field configuration
  parentId?: string; // Parent field ID for nested fields
  level: number; // Nesting level (0 = root)
}
