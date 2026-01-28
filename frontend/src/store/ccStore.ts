import { create } from 'zustand';
import { ccService } from '../api/services/cc.service';
import { CCState, CCAddDeviceRequest, CCDevice } from '../types/cc.types';
import { Simulator } from '../types/simulator.types';
import useFormStore from './useFormStore';

// Session storage keys
const CC_DEVICES_KEY = 'cc_devices';
const CC_DEVICES_CC_IP_KEY = 'cc_devices_cc_ip';
const SAPRO_SIMULATORS_KEY = 'sapro_simulators';

// Session storage helpers for devices
const getStoredDevices = (ccIp: string): CCDevice[] | null => {
  try {
    const storedCcIp = sessionStorage.getItem(CC_DEVICES_CC_IP_KEY);
    const storedDevices = sessionStorage.getItem(CC_DEVICES_KEY);

    // Only use cached data if CC IP matches
    if (storedCcIp === ccIp && storedDevices) {
      return JSON.parse(storedDevices);
    }
    return null;
  } catch (err) {
    console.error('Failed to get devices from session storage:', err);
    return null;
  }
};

const setStoredDevices = (ccIp: string, devices: CCDevice[]): void => {
  try {
    sessionStorage.setItem(CC_DEVICES_CC_IP_KEY, ccIp);
    sessionStorage.setItem(CC_DEVICES_KEY, JSON.stringify(devices));
  } catch (err) {
    console.error('Failed to store devices in session storage:', err);
  }
};

const clearStoredDevices = (): void => {
  try {
    sessionStorage.removeItem(CC_DEVICES_CC_IP_KEY);
    sessionStorage.removeItem(CC_DEVICES_KEY);
  } catch (err) {
    console.error('Failed to clear devices from session storage:', err);
  }
};

// Session storage helpers for Sapro simulators
const getStoredSaproSimulators = (): Simulator[] | null => {
  try {
    const stored = sessionStorage.getItem(SAPRO_SIMULATORS_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch (err) {
    console.error('Failed to get Sapro simulators from session storage:', err);
    return null;
  }
};

const setStoredSaproSimulators = (simulators: Simulator[]): void => {
  try {
    sessionStorage.setItem(SAPRO_SIMULATORS_KEY, JSON.stringify(simulators));
  } catch (err) {
    console.error('Failed to store Sapro simulators:', err);
  }
};

const clearStoredSaproSimulators = (): void => {
  try {
    sessionStorage.removeItem(SAPRO_SIMULATORS_KEY);
  } catch (err) {
    console.error('Failed to clear Sapro simulators:', err);
  }
};

export const useCCStore = create<CCState>((set, get) => ({
  currentCC: null,
  devices: [],
  saproSimulators: [],
  managementPorts: [],
  isLoading: false,
  error: null,

  login: async (cc_ip: string, username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.login(cc_ip, username, password);
      set({ currentCC: cc_ip });
      // Clear form state when switching to a different CC
      useFormStore.getState().clearAllFormState();

      // Pass skipLoadingState: true to prevent flickering during login flow
      await get().fetchSaproSimulators();
      await get().fetchDevices(cc_ip, false, true);  // skipLoadingState: true
      await get().fetchManagementPorts(cc_ip, true);  // skipLoadingState: true

      // Set isLoading false only after ALL operations complete
      set({ isLoading: false });
      return true;
    } catch (error: any) {
      // Prefer detailed backend validation/message (detail), then message, then generic text
      const message = error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'Login failed';
      set({ error: message, isLoading: false });
      // Return false to indicate login did not succeed. The store records the error message.
      return false;
    }
  },

  logout: async (cc_ip: string) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.logout(cc_ip);
      // Clear form state on CC logout
      useFormStore.getState().clearAllFormState();
      // Clear session storage
      clearStoredDevices();
      clearStoredSaproSimulators();
      set({
        currentCC: null,
        devices: [],
        saproSimulators: [],
        managementPorts: [],
        isLoading: false
      });
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.message || 'Logout failed';
      set({ error: message, isLoading: false });
    }
  },

  fetchDevices: async (cc_ip: string, forceRefresh: boolean = false, skipLoadingState: boolean = false) => {
    // Check session storage first if not forcing refresh
    if (!forceRefresh) {
      const cachedDevices = getStoredDevices(cc_ip);
      if (cachedDevices) {
        console.log('Using cached CC devices from session storage');
        set({ devices: cachedDevices });
        if (!skipLoadingState) {
          set({ isLoading: false });
        }
        return;
      }
    }

    if (!skipLoadingState) {
      set({ isLoading: true, error: null });
    }

    try {
      const devices = await ccService.getDevices(cc_ip);
      set({ devices });
      if (!skipLoadingState) {
        set({ isLoading: false });
      }
      // Store in session storage
      setStoredDevices(cc_ip, devices);
    } catch (error: any) {
      // If the CC session is invalid or expired, redirect the user to the CC login
      if (error?.response?.status === 401) {
        set({ currentCC: null, devices: [], isLoading: false, error: 'No active CC session. Please login again.' });
        // Force navigation to the CC login page (bypasses app-level routing)
        window.location.href = '/cc/login';
      } else {
        const message = error?.response?.data?.detail || error?.message || 'Failed to fetch devices';
        if (!skipLoadingState) {
          set({ isLoading: false, error: message });
        } else {
          set({ error: message });
        }
      }
    }
  },

  fetchSaproSimulators: async (forceRefresh: boolean = false) => {
    // Check cache first
    if (!forceRefresh) {
      const cached = getStoredSaproSimulators();
      if (cached) {
        console.log('Using cached Sapro simulators');
        set({ saproSimulators: cached });
        return;
      }
    }

    try {
      // Call Sapro endpoint
      const response = await ccService.getSaproSimulators();
      set({ saproSimulators: response });
      setStoredSaproSimulators(response);
    } catch (error: any) {
      console.error('Failed to fetch Sapro simulators:', error);
      set({ saproSimulators: [] });
    }
  },

  fetchManagementPorts: async (cc_ip: string, skipLoadingState: boolean = false) => {
    if (!skipLoadingState) {
      set({ isLoading: true, error: null });
    }

    try {
      const ports = await ccService.getManagementPorts(cc_ip);
      set({ managementPorts: ports });
      if (!skipLoadingState) {
        set({ isLoading: false });
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || error?.message || 'Failed to fetch management ports';
      if (!skipLoadingState) {
        set({ isLoading: false, error: message });
      } else {
        set({ error: message });
      }
    }
  },

  addDevice: async (cc_ip: string, data: CCAddDeviceRequest) => {
    set({ isLoading: true, error: null });
    try {
      await ccService.addDevice(cc_ip, data);
      // Invalidate cache and refresh from server
      await get().fetchDevices(cc_ip, true); // Force refresh
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

      // Wait 2 seconds before refreshing from server
      setTimeout(() => {
        // Invalidate cache and refresh from server
        get().fetchDevices(cc_ip, true); // Force refresh
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
