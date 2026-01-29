import apiClient from '../client'

interface IRPSchema {
  mongo_id: string
  template_name: string
  version: string
  created_at: string
}

interface DownloadSchemaRequest {
  sim_version: string
  username: string
  password: string
  revert_to_original?: boolean
}

interface DownloadSchemaResponse {
  success: boolean
  message: string
  local_path?: string
  mongo_id?: string
  backup_exists?: boolean
  is_custom?: boolean
}

interface SchemaMessage {
  id: string
  name: string
}

interface MessageTemplate {
  success: boolean
  name: string
  template: Record<string, any>
  schema: Record<string, any>
}

interface IRPSendPayload {
  mongo_id: string
  message_data: {
    messages: Array<Record<string, any>>
  }
}

// New: IRP template interfaces
interface IRPTemplateData {
  name: string
  schema_id: string
  schema_name: string
  messages: Array<{
    messageType: string
    messageName: string
    data: Record<string, any>
    schema: Record<string, any>
  }>
}

interface SavedTemplate {
  id: string
  name: string
  schema_name: string
  created_at: string
}

interface LoadedTemplate {
  id: string
  name: string
  schema_id: string
  schema_name: string
  messages: Array<{
    messageType: string
    messageName: string
    data: Record<string, any>
    schema: Record<string, any>
  }>
  created_at: string
}

// Add PCAP Analyzer interfaces
interface IRPPcapAnalysisMessage {
  message_id: string
  message_name: string
  count: number
  packet_numbers: number[]
  schema_versions: number[]
}

interface IRPPcapAnalysisError {
  packet_number: number
  error: string
}

interface IRPPcapAnalysisSchemaInfo {
  schema_available: boolean
  schema_version: string | null
}

interface IRPPcapAnalysisResponse {
  total_packets: number
  irp_packets: number
  messages: IRPPcapAnalysisMessage[]
  errors: IRPPcapAnalysisError[]
  schema_info: IRPPcapAnalysisSchemaInfo
}

// Aliases to satisfy consolidated exports used elsewhere
type SchemaInfo = IRPSchema
type SchemaListItem = IRPSchema
type MessageListItem = SchemaMessage

class IRPSchemaService {
  async listSchemas(ccIp: string): Promise<IRPSchema[]> {
    const response = await apiClient.get<{ schemas: IRPSchema[] }>(`/cc/${ccIp}/irp/schemas`)
    return response.data.schemas
  }

  async deleteSchema(ccIp: string, schemaId: string): Promise<void> {
    await apiClient.delete(`/cc/${ccIp}/irp/schemas/${schemaId}`)
  }

  async downloadSchema(ccIp: string, data: DownloadSchemaRequest): Promise<DownloadSchemaResponse> {
    const response = await apiClient.post<DownloadSchemaResponse>(`/cc/${ccIp}/irp/IdsDataFormat/download`, data)
    return response.data
  }

  async listMessages(ccIp: string, schemaId: string): Promise<SchemaMessage[]> {
    const response = await apiClient.get<{ messages: SchemaMessage[] }>(
      `/cc/${ccIp}/irp/schemas/${schemaId}/messages`
    )
    return response.data.messages
  }

  async getMessageTemplate(ccIp: string, schemaId: string, messageId: string): Promise<MessageTemplate> {
    const response = await apiClient.post<MessageTemplate>(
      `/cc/${ccIp}/irp/template`,
      { mongo_id: schemaId, message_id: messageId }
    )
    return response.data
  }

  async sendMessages(ccIp: string, simulatorIps: string[], payload: IRPSendPayload): Promise<void> {
    // Send messages to multiple simulators using comma-separated IPs
    const simulatorIpsParam = simulatorIps.join(',');

    await apiClient.post(
      `/cc/${ccIp}/simulators/${simulatorIpsParam}/reporter/irp`,
      payload
    );
  }

  async sendMessagesWithProgress(
    destinationPortIp: string,
    simulatorIps: string[],
    payload: any,
    onProgress: (current: number, total: number, messageName: string, status: string) => void,
    onComplete: (successCount: number, failedCount: number, totalCount: number) => void,
    onError: (error: string) => void
  ): Promise<void> {
    return new Promise<void>(async (resolve, reject) => {
      try {
        // Use comma-separated IPs for multi-simulator support
        const simulatorIpsParam = simulatorIps.join(',');

        // 1. Get baseURL from apiClient
        const baseURL = apiClient.defaults.baseURL || 'http://localhost:8000/api';

        // 2. Build full URL with comma-separated IPs
        const url = `${baseURL}/cc/${destinationPortIp}/simulators/${simulatorIpsParam}/reporter/irp/stream`;

        // 3. Get token
        const token = localStorage.getItem('access_token') || localStorage.getItem('token');
        if (!token) {
          onError('Authentication token not found');
          reject(new Error('No auth token'));
          return;
        }

        // 4. Use fetch with POST
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errorText = await response.text();
          onError(`HTTP ${response.status}: ${errorText}`);
          reject(new Error(`HTTP ${response.status}: ${errorText}`));
          return;
        }

        // 5. Get reader
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // Track progress per simulator
        const simulatorProgress = new Map<string, {success: number, failed: number}>();
        simulatorIps.forEach(ip => {
          simulatorProgress.set(ip, {success: 0, failed: 0});
        });

        // 6-11. Read stream for all simulators
        let totalSuccessCount = 0;
        let totalFailedCount = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split('\n\n');
          buffer = messages.pop() || '';

          for (const message of messages) {
            if (message.startsWith('data: ')) {
              const dataStr = message.slice(6);
              try {
                const data = JSON.parse(dataStr);

                if (data.type === 'progress') {
                  onProgress(data.current, data.total, data.message_name, data.status);
                } else if (data.type === 'complete') {
                  // Aggregate completion events from all simulators
                  const simIp = data.simulator_ip;
                  if (simIp && simulatorProgress.has(simIp)) {
                    const progress = simulatorProgress.get(simIp)!;
                    progress.success = data.success_count || 0;
                    progress.failed = data.failed_count || 0;
                  }

                  // Check if all simulators completed
                  let allCompleted = true;
                  let newSuccessCount = 0;
                  let newFailedCount = 0;

                  simulatorProgress.forEach((progress, ip) => {
                    if (progress.success === 0 && progress.failed === 0) {
                      allCompleted = false;
                    }
                    newSuccessCount += progress.success;
                    newFailedCount += progress.failed;
                  });

                  totalSuccessCount = newSuccessCount;
                  totalFailedCount = newFailedCount;

                  if (allCompleted) {
                    onComplete(totalSuccessCount, totalFailedCount, totalSuccessCount + totalFailedCount);
                    reader.releaseLock();
                    resolve();
                    return;
                  }
                } else if (data.type === 'error') {
                  onError(data.message);
                  reader.releaseLock();
                  reject(new Error(data.message));
                  return;
                }
              } catch (err) {
                onError('Failed to parse event data');
                reader.releaseLock();
                reject(err);
                return;
              }
            }
          }
        }

        // All simulators processed
        onComplete(totalSuccessCount, totalFailedCount, totalSuccessCount + totalFailedCount);
        resolve();

      } catch (err) {
        onError('Connection error');
        reject(err);
      }
    });
  }

  // Template management methods
  async saveTemplate(currentCC: string, templateData: IRPTemplateData): Promise<{ success: boolean; template_id: string }> {
    const response = await apiClient.post(`/cc/${currentCC}/irp/templates`, templateData)
    return response.data
  }

  async listTemplates(currentCC: string): Promise<{ success: boolean; templates: SavedTemplate[] }> {
    const response = await apiClient.get(`/cc/${currentCC}/irp/templates`)
    return response.data
  }

  async loadTemplate(currentCC: string, templateId: string): Promise<{ success: boolean; template: LoadedTemplate }> {
    const response = await apiClient.get(`/cc/${currentCC}/irp/templates/${templateId}`)
    return response.data
  }

  async deleteTemplate(currentCC: string, templateId: string): Promise<{ success: boolean }> {
    const response = await apiClient.delete(`/cc/${currentCC}/irp/templates/${templateId}`)
    return response.data
  }

  // Add PCAP analyzer method
  async analyzePcap(file: File, schemaId?: string): Promise<IRPPcapAnalysisResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (schemaId) {
      formData.append('schema_id', schemaId)
    }

    const response = await apiClient.post<IRPPcapAnalysisResponse>(
      '/reporter/irp/analyze-pcap',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )

    return response.data
  }
}

export const irpSchemaService = new IRPSchemaService()

// Export all public types from this module in a single statement
export type {
  IRPSchema,
  DownloadSchemaRequest,
  DownloadSchemaResponse,
  SchemaMessage,
  MessageTemplate,
  IRPSendPayload,
  IRPTemplateData,
  SavedTemplate,
  LoadedTemplate,
  SchemaInfo,
  SchemaListItem,
  MessageListItem,
  IRPPcapAnalysisMessage,
  IRPPcapAnalysisError,
  IRPPcapAnalysisSchemaInfo,
  IRPPcapAnalysisResponse,
}
