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

export const fetchStructureTemplate = async (
  ccIp: string,
  structureId: string
): Promise<any> => {
  const response = await apiClient.get<any>(
    `/cc/${ccIp}/reporter/polling/structures/${structureId}`
  );
  return response.data;
};

export const listStructureTemplates = async (
  ccIp: string
): Promise<any[]> => {
  const response = await apiClient.get<any[]>(
    `/cc/${ccIp}/reporter/polling/structures`
  );
  return response.data;
};

export const saveXmfToSimulator = async (
  ccIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  const response = await apiClient.post<PollingResponse>(
    `/cc/${ccIp}/reporter/polling/save-xmf`,
    payload
  );
  return response.data;
};

export const setPollingConfig = async (
  ccIp: string,
  simulatorIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  // Extended timeout: Supports multiple simulators (comma-separated IPs), each update_device takes up to 90s
  const response = await apiClient.post<PollingResponse>(
    `/cc/${ccIp}/simulators/${simulatorIp}/reporter/polling`,
    payload,
    { timeout: 600000 }
  );
  return response.data;
};

export const createTemplate = async (
  ccIp: string,
  template: PollingTemplateCreate
): Promise<TemplateCreateResponse> => {
  const response = await apiClient.post<TemplateCreateResponse>(
    `/cc/${ccIp}/polling/templates`,
    template
  );
  return response.data;
};

export const listTemplates = async (
  ccIp: string
): Promise<TemplateListResponse> => {
  const response = await apiClient.get<TemplateListResponse>(
    `/cc/${ccIp}/polling/templates`
  );
  return response.data;
};

export const getTemplate = async (
  ccIp: string,
  templateId: string
): Promise<TemplateDetailResponse> => {
  const response = await apiClient.get<TemplateDetailResponse>(
    `/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};

export const deleteTemplate = async (
  ccIp: string,
  templateId: string
): Promise<{ success: boolean; message: string }> => {
  const response = await apiClient.delete<{ success: boolean; message: string }>(
    `/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};
