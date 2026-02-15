import apiClient from '../client';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../../types/simulator.types';

export const simulatorService = {
  getSimulators: async (): Promise<Simulator[]> => {
    const response = await apiClient.get<Simulator[]>('/simulators');
    return response.data;
  },

  getSimulator: async (ip: string): Promise<Simulator> => {
    const response = await apiClient.get<Simulator>(`/simulators/${ip}`);
    return response.data;
  },

  createSimulator: async (data: SimulatorCreate): Promise<Simulator> => {
    // Backend handles both single IP and IP range (e.g., "192.168.1.1" or "192.168.1.1-192.168.1.25")
    const payload: any = {
      ip_address: data.ip_address,
      map: data.map,
      template_id: (data as any).template_id || data.template_id,
    };
    // Extended timeout: create_device verifies device is running (up to 90s)
    const response = await apiClient.post<Simulator>('/simulators', payload, { timeout: 120000 });
    return response.data;
  },

  createSimulatorWithProgress: async (
    data: SimulatorCreate,
    onProgress: (current: number, total: number, ip: string, status: string, message: string) => void,
    onComplete: (successCount: number, failedCount: number, totalCount: number) => void,
    onError: (error: string) => void
  ): Promise<void> => {
    return new Promise<void>(async (resolve, reject) => {
      try {
        // 1. Get baseURL from apiClient
        const baseURL = apiClient.defaults.baseURL || 'http://localhost:8000/api';

        // 2. Build full URL
        const url = `${baseURL}/simulators/stream`;

        // 3. Get token
        const token = localStorage.getItem('token');
        if (!token) {
          throw new Error('No authentication token found');
        }

        // 4. Build payload
        const payload = {
          ip_address: data.ip_address,
          map: data.map,
          template_id: data.template_id,
        };

        // 5. Start fetch with SSE
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || `HTTP error! status: ${response.status}`);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        // 6-11. Read stream
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
                  onProgress(data.current, data.total, data.ip, data.status, data.message);
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

  updateSimulator: async (ip: string, data: SimulatorUpdate): Promise<Simulator> => {
    const payload: any = {};
    if (data.map !== undefined) payload.map = data.map;
    if (data.template_id !== undefined) payload.template_id = data.template_id;

    // Extended timeout: update_device (delete + create) verifies device is running (up to 90s)
    const response = await apiClient.put<Simulator>(`/simulators/${ip}`, payload, { timeout: 120000 });
    return response.data;
  },

  deleteSimulator: async (ip: string): Promise<void> => {
    await apiClient.delete(`/simulators/${ip}`);
    return;
  },
};
