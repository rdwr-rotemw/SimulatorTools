import { create } from 'zustand';
import { ccService, ManagementPort } from '../api/services/cc.service';
import { CCState, CCAddDeviceRequest, ManagementPort as ManagementPortType } from '../types/cc.types';

export const useCCStore = create<CCState>((set, get) => ({
  currentCC: null,
  devices: [],
  managementPorts: [],
  isLoading: false,
  error: null,

  login: async (cc_ip: string, username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.login(cc_ip, username, password);
      set({ currentCC: cc_ip, isLoading: false });
      // Fetch devices immediately after login
      await get().fetchDevices(cc_ip);
      // Also fetch management ports right after login
      await get().fetchManagementPorts(cc_ip);
      return true;
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.message || 'Login failed';
      set({ error: message, isLoading: false });
      // Return false to indicate login did not succeed. The store records the error message.
      return false;
    }
  },

  logout: async (cc_ip: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.logout(cc_ip);
      set({ currentCC: null, devices: [], isLoading: false });
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.message || 'Logout failed';
      set({ error: message, isLoading: false });
    }
  },

  fetchDevices: async (cc_ip: string) => {
    set({ isLoading: true, error: null });
    try {
      const devices = await ccService.getDevices(cc_ip);
      set({ devices, isLoading: false });
    } catch (error: any) {
      // If the CC session is invalid or expired, redirect the user to the CC login
      if (error?.response?.status === 401) {
        set({ currentCC: null, devices: [], isLoading: false, error: 'No active CC session. Please login again.' });
        // Force navigation to the CC login page (bypasses app-level routing)
        window.location.href = '/cc/login';
      } else {
        const message = error?.response?.data?.detail || error?.message || 'Failed to fetch devices';
        set({ isLoading: false, error: message });
      }
    }
  },

  fetchManagementPorts: async (cc_ip: string) => {
    set({ isLoading: true, error: null });
    try {
      const ports = await ccService.getManagementPorts(cc_ip);
      set({ managementPorts: ports, isLoading: false });
    } catch (error: any) {
      const message = error?.response?.data?.detail || error?.message || 'Failed to fetch management ports';
      set({ isLoading: false, error: message });
    }
  },

  addDevice: async (cc_ip: string, data: CCAddDeviceRequest) => {
    set({ isLoading: true, error: null });
    try {
      const created = await ccService.addDevice(cc_ip, data);
      set((state) => ({ devices: [...state.devices, created], isLoading: false }));
    } catch (error: any) {
      const message = error?.response?.data?.detail || error?.message || 'Failed to add device';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  deleteDevice: async (cc_ip: string, device_id: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.deleteDevice(cc_ip, device_id);

      // Wait 2 seconds before updating state and refreshing
      setTimeout(() => {
        set((state) => ({
          devices: state.devices.filter((d) => d.device_id !== device_id),
          isLoading: false
        }));
        // Refresh entire devices list
        get().fetchDevices(cc_ip);
      }, 2000);

    } catch (error: any) {
      const message = error?.response?.data?.detail || error?.message || 'Failed to delete device';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  clearError: () => set({ error: null }),

  clearState: () => set({ currentCC: null, devices: [], error: null }),
}));

export default useCCStore;
