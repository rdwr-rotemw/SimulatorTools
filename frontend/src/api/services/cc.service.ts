import apiClient from '../client';
import { CCLoginRequest, CCLoginResponse, CCDevice, CCAddDeviceRequest, CCDeleteResponse } from '../../types/cc.types';

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

  addDevice: async (cc_ip: string, data: CCAddDeviceRequest): Promise<CCDevice> => {
    const response = await apiClient.post<CCDevice>(`/cc/${cc_ip}/simulators`, data);
    return response.data;
  },

  getManagementPorts: async (cc_ip: string): Promise<ManagementPort[]> => {
    const response = await apiClient.get<{ ports: ManagementPort[] }>(`/cc/${cc_ip}/management-ports`);
    return response.data.ports;
  },

  deleteDevice: async (cc_ip: string, simulator_ip: string): Promise<CCDeleteResponse> => {
    const response = await apiClient.delete<CCDeleteResponse>(`/cc/${cc_ip}/simulators/${simulator_ip}`);
    return response.data;
  },
};
