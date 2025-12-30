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
    // Backend expects a `template` string field; translate frontend's template_id into `template`.
    const payload: any = {
      ip_address: data.ip_address,
      map: data.map,
      template_id: (data as any).template_id || data.template_id,
    };
    const response = await apiClient.post<Simulator>('/simulators', payload);
    return response.data;
  },

  updateSimulator: async (ip: string, data: SimulatorUpdate): Promise<Simulator> => {
    const payload: any = {};
    if (data.map !== undefined) payload.map = data.map;
    if (data.template_id !== undefined) payload.template_id = data.template_id;

    const response = await apiClient.put<Simulator>(`/simulators/${ip}`, payload);
    return response.data;
  },

  deleteSimulator: async (ip: string): Promise<void> => {
    await apiClient.delete(`/simulators/${ip}`);
    return;
  },
};
