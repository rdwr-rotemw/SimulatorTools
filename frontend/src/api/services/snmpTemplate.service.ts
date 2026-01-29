import apiClient from '../client';
import { SNMPTrap } from '../../types/snmp.types';
import useCCStore from '../../store/ccStore';

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

  async sendTraps(destinationPortIp: string, simulatorIps: string[], traps: SNMPTrap[]): Promise<void> {
    // Send traps to multiple simulators using comma-separated IPs and map dict
    const saproSimulators = useCCStore.getState().saproSimulators;

    // Build map dict for all simulators
    const mapDict: Record<string, string> = {};
    for (const simulatorIp of simulatorIps) {
      const saproSim = saproSimulators.find(sim => sim.ip_address === simulatorIp);
      if (!saproSim || !saproSim.map) {
        throw new Error(`No map found for simulator ${simulatorIp}`);
      }
      mapDict[simulatorIp] = saproSim.map;
    }

    // Use comma-separated IPs in URL
    const simulatorIpsParam = simulatorIps.join(',');
    const url = `/cc/${destinationPortIp}/simulators/${simulatorIpsParam}/reporter/snmp`;

    await apiClient.post(url, {
      map: mapDict, // Send as dict for multi-simulator
      traps
    }, {
      timeout: 600000, // 10 minutes - allows for pause delays and multiple traps
    });
  }

  async sendTrapsWithProgress(
    destinationPortIp: string,
    simulatorIps: string[],
    traps: SNMPTrap[],
    onProgress: (current: number, total: number, trapName: string, status: string) => void,
    onComplete: (successCount: number, failedCount: number, totalCount: number) => void,
    onError: (error: string) => void
  ): Promise<void> {
    return new Promise<void>(async (resolve, reject) => {
      try {
        const saproSimulators = useCCStore.getState().saproSimulators;

        // Build map dict for all simulators
        const mapDict: Record<string, string> = {};
        for (const simulatorIp of simulatorIps) {
          const saproSim = saproSimulators.find(sim => sim.ip_address === simulatorIp);
          if (!saproSim || !saproSim.map) {
            onError(`No map found for simulator ${simulatorIp}`);
            reject(new Error(`No map found for simulator ${simulatorIp}`));
            return;
          }
          mapDict[simulatorIp] = saproSim.map;
        }

        // Use comma-separated IPs for multi-simulator support
        const simulatorIpsParam = simulatorIps.join(',');

        // 1. Get baseURL from apiClient
        const baseURL = apiClient.defaults.baseURL || 'http://localhost:8000/api';

        // 2. Build full URL with comma-separated IPs
        const url = `${baseURL}/cc/${destinationPortIp}/simulators/${simulatorIpsParam}/reporter/snmp/stream`;

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
            map: mapDict, // Send as dict for multi-simulator
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
                  onProgress(data.current, data.total, data.trap_name, data.status);
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
}

export const snmpTemplateService = new SNMPTemplateService();
