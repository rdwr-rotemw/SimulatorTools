import apiClient from '../client';
import { CCLoginRequest, CCLoginResponse, CCDevice, CCAddDeviceRequest, CCDeleteResponse } from '../../types/cc.types';
import { Simulator } from '../../types/simulator.types';

export interface ManagementPort {
  interface: string;
  address: string;
}

export const ccService = {
  login: async (cc_ip: string, username: string, password: string): Promise<CCLoginResponse> => {
    const response = await apiClient.post<CCLoginResponse>(`/cc/${cc_ip}/login`, { username, password } as CCLoginRequest);
    return response.data;
  },

  logout: async (cc_ip: string): Promise<CCDeleteResponse> => {
    const response = await apiClient.post<CCDeleteResponse>(`/cc/${cc_ip}/logout`);
    return response.data;
  },

  getDevices: async (cc_ip: string): Promise<CCDevice[]> => {
    const response = await apiClient.get<{ devices: CCDevice[] }>(`/cc/${cc_ip}/simulators`);
    return response.data.devices;
  },

  getSaproSimulators: async (): Promise<Simulator[]> => {
    const response = await apiClient.get<Simulator[]>('/simulators');
    return response.data;
  },

  addDeviceWithStatusCheck: async (
    cc_ip: string,
    data: CCAddDeviceRequest,
    onProgress: (current: number, total: number, ip: string, name: string, status: 'adding' | 'added' | 'checking' | 'success' | 'failed', message: string) => void,
    onComplete: (successCount: number, failedCount: number, totalCount: number) => void,
    onError: (error: string) => void
  ): Promise<void> => {
    return new Promise<void>(async (resolve, reject) => {
      try {
        // 1. Get baseURL from apiClient
        const baseURL = apiClient.defaults.baseURL || 'http://localhost:8000/api';

        // 2. Build full URL
        const url = `${baseURL}/cc/${cc_ip}/simulators/stream-with-status`;

        // 3. Get token
        const token = localStorage.getItem('token');
        if (!token) {
          throw new Error('No authentication token found');
        }

        // 4. Start fetch with SSE
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || `HTTP error! status: ${response.status}`);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        // 5. Read stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

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
                  onProgress(data.current, data.total, data.ip, data.name, data.status, data.message);
                } else if (data.type === 'phase') {
                  // Optional: show phase transition message
                  console.log(data.message);
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
              } catch (parseErr) {
                console.error('Failed to parse SSE message:', parseErr, 'Raw:', dataStr);
              }
            }
          }
        }

        reader.releaseLock();
        resolve();
      } catch (err: any) {
        console.error('Stream error:', err);
        onError(err.message || 'Unknown error');
        reject(err);
      }
    });
  },

  getManagementPorts: async (cc_ip: string): Promise<ManagementPort[]> => {
    const response = await apiClient.get<{ ports: ManagementPort[] }>(`/cc/${cc_ip}/management-ports`);
    return response.data.ports;
  },

  deleteDevice: async (cc_ip: string, device_id: string): Promise<CCDeleteResponse> => {
    const response = await apiClient.delete<CCDeleteResponse>(`/cc/${cc_ip}/simulators/${device_id}`);
    return response.data;
  },
};
