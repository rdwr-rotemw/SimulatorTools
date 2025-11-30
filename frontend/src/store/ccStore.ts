import { create } from 'zustand';
import { ccService } from '../api/services/cc.service';
import { CCState, CCAddDeviceRequest } from '../types/cc.types';

export const useCCStore = create<CCState>((set) => ({
  currentCC: null,
  devices: [],
  isLoading: false,
  error: null,

  login: async (cc_ip: string, username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.login(cc_ip, username, password);
      set({ currentCC: cc_ip, isLoading: false });
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.message || 'Login failed';
      set({ error: message, isLoading: false });
      throw error;
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

  deleteDevice: async (cc_ip: string, simulator_ip: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.deleteDevice(cc_ip, simulator_ip);
      set((state) => ({ devices: state.devices.filter((d) => d.management_ip !== simulator_ip), isLoading: false }));
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
