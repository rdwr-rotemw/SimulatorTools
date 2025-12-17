import { create } from 'zustand';
import { simulatorService } from '../api/services/simulator.service';
import { SimulatorState, SimulatorCreate, SimulatorUpdate } from '../types/simulator.types';

export const useSimulatorStore = create<SimulatorState>((set, get) => ({
  simulators: [],
  selectedSimulator: null,
  isLoading: false,
  error: null,

  fetchSimulators: async () => {
    set({ isLoading: true, error: null });
    try {
      const sims = await simulatorService.getSimulators();
      set({ simulators: sims, isLoading: false });
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to fetch simulators';
      set({ error: message, isLoading: false });
    }
  },

  fetchSimulator: async (ip: string) => {
    set({ isLoading: true, error: null });
    try {
      const sim = await simulatorService.getSimulator(ip);
      set({ selectedSimulator: sim, isLoading: false });
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to fetch simulator';
      set({ error: message, isLoading: false });
    }
  },

  createSimulator: async (data: SimulatorCreate) => {
    set({ isLoading: true, error: null });
    try {
      const created = await simulatorService.createSimulator(data);
      set((state) => ({ simulators: [...state.simulators, created], isLoading: false }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to create simulator';
      set({ error: message, isLoading: false });
    }
  },

  updateSimulator: async (ip: string, data: SimulatorUpdate) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await simulatorService.updateSimulator(ip, data);
      set((state) => ({
        simulators: state.simulators.map((s) => (s.ip_address === ip ? updated : s)),
        isLoading: false,
      }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to update simulator';
      set({ error: message, isLoading: false });
    }
  },

  deleteSimulator: async (ip: string) => {
    set({ isLoading: true, error: null });
    try {
      await simulatorService.deleteSimulator(ip);
      set((state) => ({ simulators: state.simulators.filter((s) => s.ip_address !== ip), isLoading: false }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Failed to delete simulator';
      set({ error: message, isLoading: false });
      // Re-throw so caller (page) can show an error snackbar or take other actions
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));

export default useSimulatorStore;
