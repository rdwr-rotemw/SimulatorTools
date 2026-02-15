/**
 * Polling API client functions.
 *
 * Provides type-safe async functions for:
 * - Saving XMF files to Sapro filesystem
 * - Setting polling configuration on simulators
 * - Managing polling templates (CRUD operations)
 * - Fetching polling structure templates
 */

import apiClient from '../client';
import {
  PollingPayload,
  PollingResponse,
  PollingTemplateCreate,
  TemplateListResponse,
  TemplateDetailResponse,
  TemplateCreateResponse,
} from '../../types/polling';

// API base URL - defaults to /api but can be configured via environment
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';

/**
 * Fetch polling structure template by structure_id.
 *
 * Structure templates define the data structure for a specific endpoint type
 * (e.g., attack_data, application_traffic_v1, etc.)
 *
 * @param ccIp - CyberController IP address
 * @param structureId - Structure identifier (e.g., 'attack_data')
 * @returns Promise with structure template containing _type and _properties
 */
export const fetchStructureTemplate = async (
  ccIp: string,
  structureId: string
): Promise<any> => {
  const response = await apiClient.get<any>(
    `${API_BASE_URL}/cc/${ccIp}/reporter/polling/structures/${structureId}`
  );
  return response.data;
};

/**
 * List all available polling structure templates.
 *
 * Returns all structure templates available on the system.
 *
 * @param ccIp - CyberController IP address
 * @returns Promise with array of all structure templates
 */
export const listStructureTemplates = async (
  ccIp: string
): Promise<any[]> => {
  const response = await apiClient.get<any[]>(
    `${API_BASE_URL}/cc/${ccIp}/reporter/polling/structures`
  );
  return response.data;
};

/**
 * Save XMF file to Sapro filesystem (does NOT load to simulator).
 *
 * Use this when you want to prepare an XMF configuration file
 * for later manual use or review.
 *
 * @param ccIp - CyberController IP address
 * @param payload - Polling payload with template_id or endpoint_config and xmf_filename
 * @returns Promise with success status and file path
 */
export const saveXmfToSimulator = async (
  ccIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  const response = await apiClient.post<PollingResponse>(
    `${API_BASE_URL}/cc/${ccIp}/reporter/polling/save-xmf`,
    payload
  );
  return response.data;
};

/**
 * Set polling configuration on simulator (saves XMF and loads to device).
 *
 * This is the full flow that:
 * 1. Generates XMF from template or config
 * 2. Saves XMF to Sapro filesystem
 * 3. Creates DeviceMap XML
 * 4. Loads to simulator via update_device()
 * 5. Simulator starts responding immediately
 *
 * @param ccIp - CyberController IP address
 * @param simulatorIp - Target simulator IP address
 * @param payload - Polling payload with template_id or endpoint_config and xmf_filename
 * @returns Promise with success status and message
 */
export const setPollingConfig = async (
  ccIp: string,
  simulatorIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  // Extended timeout: Supports multiple simulators (comma-separated IPs), each update_device takes up to 90s
  const response = await apiClient.post<PollingResponse>(
    `${API_BASE_URL}/cc/${ccIp}/simulators/${simulatorIp}/reporter/polling`,
    payload,
    { timeout: 600000 }
  );
  return response.data;
};

/**
 * Create a new polling template.
 *
 * Templates are stored in MongoDB and can be reused across multiple simulators.
 *
 * @param ccIp - CyberController IP address
 * @param template - Template data (name, description, endpoint config)
 * @returns Promise with template ID and success message
 */
export const createTemplate = async (
  ccIp: string,
  template: PollingTemplateCreate
): Promise<TemplateCreateResponse> => {
  const response = await apiClient.post<TemplateCreateResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates`,
    template
  );
  return response.data;
};

/**
 * List all polling templates.
 *
 * Returns lightweight summaries without full endpoint configurations.
 * Use getTemplate() to fetch full details.
 *
 * @param ccIp - CyberController IP address
 * @returns Promise with array of template summaries
 */
export const listTemplates = async (
  ccIp: string
): Promise<TemplateListResponse> => {
  const response = await apiClient.get<TemplateListResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates`
  );
  return response.data;
};

/**
 * Get polling template details by ID.
 *
 * Returns the full template including endpoint configuration
 * and all field definitions.
 *
 * @param ccIp - CyberController IP address
 * @param templateId - MongoDB template ID
 * @returns Promise with full template details
 */
export const getTemplate = async (
  ccIp: string,
  templateId: string
): Promise<TemplateDetailResponse> => {
  const response = await apiClient.get<TemplateDetailResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};

/**
 * Delete a polling template.
 *
 * Permanently removes the template from MongoDB.
 * This does not affect XMF files that were already generated from it.
 *
 * @param ccIp - CyberController IP address
 * @param templateId - MongoDB template ID
 * @returns Promise with success status
 */
export const deleteTemplate = async (
  ccIp: string,
  templateId: string
): Promise<{ success: boolean; message: string }> => {
  const response = await apiClient.delete<{ success: boolean; message: string }>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};
