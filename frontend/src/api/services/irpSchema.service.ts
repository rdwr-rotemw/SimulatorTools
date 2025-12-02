import apiClient from '../client'

export interface IRPSchema {
  mongo_id: string
  template_name: string
  version: string
  created_at: string
}

export interface DownloadSchemaRequest {
  sim_version: string
  username: string
  password: string
}

export interface DownloadSchemaResponse {
  success: boolean
  message: string
  local_path: string
  mongo_id: string
}

export interface SchemaMessage {
  id: string
  name: string
}

export interface MessageTemplate {
  success: boolean
  name: string
  template: Record<string, any>
}

export interface IRPSendPayload {
  mongo_id: string
  message_data: {
    messages: Array<Record<string, any>>
  }
}

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
}

export const irpSchemaService = new IRPSchemaService()
