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
}

interface DownloadSchemaResponse {
  success: boolean
  message: string
  local_path: string
  mongo_id: string
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

  async sendMessages(ccIp: string, simulatorIp: string, payload: IRPSendPayload): Promise<void> {
    await apiClient.post(
      `/cc/${ccIp}/simulators/${simulatorIp}/reporter/irp`,
      payload
    )
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
}
