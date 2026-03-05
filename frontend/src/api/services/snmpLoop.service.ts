import apiClient from '../client';

export interface SNMPLoopStatus {
  is_active: boolean;
  loop_delay: number | null;
  loop_timeout: number | null;
  start_time: string | null;
  batches_sent: number;
  failed_batches: number;
  traps_sent: number;
  failed_traps: number;
  last_error: string | null;
  elapsed_seconds: number;
  remaining_seconds: number;
  simulators: string[];
  destination_port: string | null;
}

export interface SNMPLoopStartRequest {
  cc_ip: string;
  loop_delay: number;
  loop_timeout: number;
  simulators: string[];
  simulator_maps: Record<string, string>;
  destination_port: string;
  traps: any[];
  configured_attack_ids?: Record<string, string[]> | null;
  regenerate_attack_id?: boolean;
}

export interface SNMPLoopStartResponse {
  success: boolean;
  message: string;
  loop_delay: number;
  loop_timeout: number;
  batches_sent: number;
}

export interface SNMPLoopStopResponse {
  success: boolean;
  message: string;
  batches_sent: number;
  elapsed_seconds: number;
}

export interface ActiveLoopInfo {
  user_id: string;
  traps_per_15s: number;
  remaining_seconds: number;
  simulators_count: number;
  loop_delay: number;
}

export interface CapacityInfo {
  system_capacity: number;
  current_usage: number;
  requested: number;
  available: number;
  max_traps: number;
  active_loops: ActiveLoopInfo[];
}

export const snmpLoopService = {
  /**
   * Get the current SNMP loop status for the authenticated user
   */
  async getStatus(): Promise<SNMPLoopStatus> {
    const response = await apiClient.get<SNMPLoopStatus>('/reporter/snmp/loop/status');
    return response.data;
  },

  /**
   * Start a new SNMP loop
   */
  async startLoop(request: SNMPLoopStartRequest): Promise<SNMPLoopStartResponse> {
    const response = await apiClient.post<SNMPLoopStartResponse>(
      '/reporter/snmp/loop/start',
      request
    );
    return response.data;
  },

  /**
   * Stop the current SNMP loop
   */
  async stopLoop(): Promise<SNMPLoopStopResponse> {
    const response = await apiClient.post<SNMPLoopStopResponse>('/reporter/snmp/loop/stop');
    return response.data;
  },
};
