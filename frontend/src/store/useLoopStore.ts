import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface LoopConfig {
  isLooping: boolean;
  loopDelay: number;
  loopTimeout: number;
  startTime: number | null;
  batchesSent: number;
  simulator: string[];
  destinationPort: string;
}

interface LoopState {
  snmp: LoopConfig;
  irp: LoopConfig;
}

interface LoopStore extends LoopState {
  // SNMP loop methods
  getSnmpLoopState: () => LoopConfig;
  setSnmpLoopState: (state: Partial<LoopConfig>) => void;
  clearSnmpLoop: () => void;
  isSnmpLooping: () => boolean;

  // IRP loop methods
  getIrpLoopState: () => LoopConfig;
  setIrpLoopState: (state: Partial<LoopConfig>) => void;
  clearIrpLoop: () => void;
  isIrpLooping: () => boolean;

  // Time calculation methods
  getElapsedTime: (pageType: 'snmp' | 'irp') => number;
  getRemainingTime: (pageType: 'snmp' | 'irp') => number;

  // Increment batch counter
  incrementSnmpBatches: () => void;
  incrementIrpBatches: () => void;
}

const defaultLoopConfig: LoopConfig = {
  isLooping: false,
  loopDelay: 15,
  loopTimeout: 600,
  startTime: null,
  batchesSent: 0,
  simulator: [],
  destinationPort: '',
};

const useLoopStore = create<LoopStore>()(
  persist(
    (set, get) => ({
      // Initial state
      snmp: { ...defaultLoopConfig },
      irp: { ...defaultLoopConfig },

      // SNMP loop methods
      getSnmpLoopState: () => get().snmp,

      setSnmpLoopState: (state: Partial<LoopConfig>) => {
        set((prev) => ({
          snmp: { ...prev.snmp, ...state },
        }));
      },

      clearSnmpLoop: () => {
        set({ snmp: { ...defaultLoopConfig } });
      },

      isSnmpLooping: () => get().snmp.isLooping,

      incrementSnmpBatches: () => {
        set((prev) => ({
          snmp: { ...prev.snmp, batchesSent: prev.snmp.batchesSent + 1 },
        }));
      },

      // IRP loop methods
      getIrpLoopState: () => get().irp,

      setIrpLoopState: (state: Partial<LoopConfig>) => {
        set((prev) => ({
          irp: { ...prev.irp, ...state },
        }));
      },

      clearIrpLoop: () => {
        set({ irp: { ...defaultLoopConfig } });
      },

      isIrpLooping: () => get().irp.isLooping,

      incrementIrpBatches: () => {
        set((prev) => ({
          irp: { ...prev.irp, batchesSent: prev.irp.batchesSent + 1 },
        }));
      },

      // Time calculation methods
      getElapsedTime: (pageType: 'snmp' | 'irp') => {
        const loopConfig = get()[pageType];
        if (!loopConfig.startTime) return 0;
        return Math.floor((Date.now() - loopConfig.startTime) / 1000);
      },

      getRemainingTime: (pageType: 'snmp' | 'irp') => {
        const loopConfig = get()[pageType];
        if (!loopConfig.startTime) return loopConfig.loopTimeout;
        const elapsed = Math.floor((Date.now() - loopConfig.startTime) / 1000);
        const remaining = loopConfig.loopTimeout - elapsed;
        return Math.max(0, remaining);
      },
    }),
    {
      name: 'simulator-tools-loop-state',
      partialize: (state) => ({
        snmp: state.snmp,
        irp: state.irp,
      }),
    }
  )
);

export default useLoopStore;
export type { LoopConfig, LoopState, LoopStore };

