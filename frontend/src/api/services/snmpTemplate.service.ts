import apiClient from '../client';
import { SNMPTrap } from '../../types/snmp.types';

export interface SNMPTemplateListItem {
  name: string;
  created_at: string;
  trap_count: number;
}

export interface SNMPTemplate {
  name: string;
  traps: SNMPTrap[];
  user_id?: number;
  cc_ip?: string;
  created_at?: string;
}

class SNMPTemplateService {
  private getBaseUrl(ccIp: string): string {
    return `/cc/${ccIp}/reporter/snmp`;
  }

  async saveTemplate(ccIp: string, name: string, traps: SNMPTrap[]): Promise<void> {
    const url = `${this.getBaseUrl(ccIp)}/templates`;
    await apiClient.post(url, { name, traps });
  }

  async listTemplates(ccIp: string): Promise<SNMPTemplateListItem[]> {
    const url = `${this.getBaseUrl(ccIp)}/templates`;
    const response = await apiClient.get<SNMPTemplateListItem[]>(url);
    return response.data;
  }

  async getTemplate(ccIp: string, templateName: string): Promise<SNMPTemplate> {
    const url = `${this.getBaseUrl(ccIp)}/templates/${encodeURIComponent(templateName)}`;
    const response = await apiClient.get<SNMPTemplate>(url);
    return response.data;
  }

  async deleteTemplate(ccIp: string, templateName: string): Promise<void> {
    const url = `${this.getBaseUrl(ccIp)}/templates/${encodeURIComponent(templateName)}`;
    await apiClient.delete(url);
  }

  async sendTraps(destinationPortIp: string, simulatorIp: string, simulatorMap: string, traps: SNMPTrap[]): Promise<void> {
    const url = `/cc/${destinationPortIp}/simulators/${simulatorIp}/reporter/snmp`;
    await apiClient.post(url, {
      map: simulatorMap,
      traps
    }, {
      timeout: 600000, // 10 minutes - allows for pause delays and multiple traps
    });
  }

  async sendTrapsWithProgress(
    destinationPortIp: string,
    simulatorIp: string,
    simulatorMap: string,
    traps: SNMPTrap[],
    onProgress: (current: number, total: number, trapName: string, status: string) => void,
    onComplete: (successCount: number, failedCount: number, totalCount: number) => void,
    onError: (error: string) => void
  ): Promise<void> {
    return new Promise<void>(async (resolve, reject) => {
      try {
        // 1. Get baseURL from apiClient
        const baseURL = apiClient.defaults.baseURL || 'http://localhost:8000/api';

        // 2. Build full URL
        const url = `${baseURL}/cc/${destinationPortIp}/simulators/${simulatorIp}/reporter/snmp/stream`;

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
          body: JSON.stringify({
            map: simulatorMap,
            traps
          })
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

        // 6-11. Read stream
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
                  onProgress(data.current, data.total, data.trap_name, data.status);
                } else if (data.type === 'complete') {
                  onComplete(data.success_count, data.failed_count, data.total_count);
                  reader.releaseLock();
                  resolve();
                  return;
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

        // If stream ends without complete, resolve anyway
        resolve();
      } catch (err) {
        onError('Connection error');
        reject(err);
      }
    });
  }
}

export const snmpTemplateService = new SNMPTemplateService();
