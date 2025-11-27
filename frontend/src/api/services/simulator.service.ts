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
    const response = await apiClient.post<Simulator>('/simulators', data);
    return response.data;
  },

  updateSimulator: async (ip: string, data: SimulatorUpdate): Promise<Simulator> => {
    const response = await apiClient.put<Simulator>(`/simulators/${ip}`, data);
    return response.data;
  },

  deleteSimulator: async (ip: string): Promise<void> => {
    await apiClient.delete(`/simulators/${ip}`);
    return;
  },
};

