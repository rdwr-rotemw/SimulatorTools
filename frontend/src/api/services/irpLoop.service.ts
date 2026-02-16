import apiClient from '../client';

export interface IRPLoopStatus {
  is_active: boolean;
  loop_delay: number | null;
  loop_timeout: number | null;
  start_time: string | null;
  batches_sent: number;
  failed_batches: number;
  last_error: string | null;
  elapsed_seconds: number;
  remaining_seconds: number;
  simulator: string | null;
  destination_port: string | null;
}

export interface IRPLoopStartRequest {
  cc_ip: string;
  loop_delay: number;
  loop_timeout: number;
  simulator: string;
  destination_port: string;
  schema_id: string;
  messages: any[];
}

export interface IRPLoopStartResponse {
  success: boolean;
  message: string;
  loop_delay: number;
  loop_timeout: number;
  batches_sent: number;
}

export interface IRPLoopStopResponse {
  success: boolean;
  message: string;
  batches_sent: number;
  elapsed_seconds: number;
}

export const irpLoopService = {
  /**
   * Get the current IRP loop status for the authenticated user
   */
  async getStatus(): Promise<IRPLoopStatus> {
    const response = await apiClient.get<IRPLoopStatus>('/reporter/irp/loop/status');
    return response.data;
  },

  /**
   * Start a new IRP loop
   */
  async startLoop(request: IRPLoopStartRequest): Promise<IRPLoopStartResponse> {
    const response = await apiClient.post<IRPLoopStartResponse>(
      '/reporter/irp/loop/start',
      request
    );
    return response.data;
  },

  /**
   * Stop the current IRP loop
   */
  async stopLoop(): Promise<IRPLoopStopResponse> {
    const response = await apiClient.post<IRPLoopStopResponse>('/reporter/irp/loop/stop');
    return response.data;
  },
};
