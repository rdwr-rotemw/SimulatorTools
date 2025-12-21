import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { SNMPTrap } from '../types/snmp.types';

/**
 * Session identifier for tracking user and CC context
 */
interface SessionInfo {
  cc: string | null;
  userId: string | null;
}

/**
 * Form state interface for SNMP and IRP forms
 */
interface FormState {
  session: SessionInfo;
  snmp: {
    traps: SNMPTrap[] | null;
    expandedTraps: number[];
  };
  irp: {
    messages: any[] | null;
    expandedMessages: number[];
  };
}

/**
 * Store interface with all methods
 */
interface FormStore extends FormState {
  // Session management methods
  setCurrentSession: (cc: string, userId?: string) => void;
  isSessionValid: (cc: string, userId?: string) => boolean;
  clearAllFormState: () => void;

  // SNMP form methods
  setSnmpFormState: (traps: SNMPTrap[], expandedTraps: number[]) => void;
  getSnmpFormState: () => { traps: SNMPTrap[] | null; expandedTraps: number[] };
  clearSnmpFormState: () => void;

  // IRP form methods
  setIrpFormState: (messages: any[], expandedMessages: number[]) => void;
  getIrpFormState: () => { messages: any[] | null; expandedMessages: number[] };
  clearIrpFormState: () => void;
}

/**
 * Zustand store for form state persistence with session awareness
 * Automatically syncs to localStorage for both SNMP and IRP forms
 * Auto-clears when session (CC + userId) changes
 */
const useFormStore = create<FormStore>()(
  persist(
    (set, get) => ({
      // Initial state
      session: {
        cc: null,
        userId: null,
      },
      snmp: {
        traps: null,
        expandedTraps: [],
      },
      irp: {
        messages: null,
        expandedMessages: [],
      },

      // Session management methods
      setCurrentSession: (cc: string, userId?: string) => {
        const state = get();
        const currentSession = state.session;

        // Check if session has changed
        if (currentSession.cc !== cc || currentSession.userId !== (userId || null)) {
          // Session changed - clear all form state and set new session
          set({
            session: {
              cc,
              userId: userId || null,
            },
            snmp: {
              traps: null,
              expandedTraps: [],
            },
            irp: {
              messages: null,
              expandedMessages: [],
            },
          });
        } else {
          // Same session - just update in case it was null before
          set({
            session: {
              cc,
              userId: userId || null,
            },
          });
        }
      },

      isSessionValid: (cc: string, userId?: string) => {
        const state = get();
        return (
          state.session.cc === cc &&
          state.session.userId === (userId || null)
        );
      },

      clearAllFormState: () => {
        set({
          session: {
            cc: null,
            userId: null,
          },
          snmp: {
            traps: null,
            expandedTraps: [],
          },
          irp: {
            messages: null,
            expandedMessages: [],
          },
        });
      },

      // SNMP form methods
      setSnmpFormState: (traps: SNMPTrap[], expandedTraps: number[]) => {
        set({
          snmp: {
            traps: JSON.parse(JSON.stringify(traps)), // Deep clone to prevent mutations
            expandedTraps: [...expandedTraps],
          },
        });
      },

      getSnmpFormState: () => {
        const state = get();
        // Return null if no session is set (user not logged in or session cleared)
        if (!state.session.cc) {
          return {
            traps: null,
            expandedTraps: [],
          };
        }
        return {
          traps: state.snmp.traps,
          expandedTraps: state.snmp.expandedTraps,
        };
      },

      clearSnmpFormState: () => {
        set({
          snmp: {
            traps: null,
            expandedTraps: [],
          },
        });
      },

      // IRP form methods
      setIrpFormState: (messages: any[], expandedMessages: number[]) => {
        set({
          irp: {
            messages: JSON.parse(JSON.stringify(messages)), // Deep clone to prevent mutations
            expandedMessages: [...expandedMessages],
          },
        });
      },

      getIrpFormState: () => {
        const state = get();
        // Return null if no session is set (user not logged in or session cleared)
        if (!state.session.cc) {
          return {
            messages: null,
            expandedMessages: [],
          };
        }
        return {
          messages: state.irp.messages,
          expandedMessages: state.irp.expandedMessages,
        };
      },

      clearIrpFormState: () => {
        set({
          irp: {
            messages: null,
            expandedMessages: [],
          },
        });
      },
    }),
    {
      name: 'simulator_tools_form_storage', // Root storage key
      storage: createJSONStorage(() => localStorage),

      // Partition storage: include session with SNMP and IRP state
      partialize: (state) => ({
        session: state.session,
        snmp: state.snmp,
        irp: state.irp,
      }),

      // Custom merge strategy to handle null values properly
      merge: (persistedState: any, currentState: FormStore) => {
        return {
          ...currentState,
          session: persistedState?.session ?? currentState.session,
          snmp: persistedState?.snmp ?? currentState.snmp,
          irp: persistedState?.irp ?? currentState.irp,
        };
      },
    }
  )
);

/**
 * Manual localStorage helpers for explicit key-based access
 * (Optional: for debugging or migration purposes)
 */
export const FormStorageKeys = {
  SNMP: 'simulator_tools_form_snmp',
  IRP: 'simulator_tools_form_irp',
};

/**
 * Manual save to specific localStorage keys (for backward compatibility)
 */
export const saveToLocalStorage = {
  snmp: (traps: SNMPTrap[], expandedTraps: number[]) => {
    localStorage.setItem(
      FormStorageKeys.SNMP,
      JSON.stringify({ traps, expandedTraps })
    );
  },
  irp: (messages: any[], expandedMessages: number[]) => {
    localStorage.setItem(
      FormStorageKeys.IRP,
      JSON.stringify({ messages, expandedMessages })
    );
  },
};

/**
 * Manual load from specific localStorage keys (for backward compatibility)
 */
export const loadFromLocalStorage = {
  snmp: (): { traps: SNMPTrap[] | null; expandedTraps: number[] } | null => {
    const stored = localStorage.getItem(FormStorageKeys.SNMP);
    if (!stored) return null;
    try {
      return JSON.parse(stored);
    } catch {
      return null;
    }
  },
  irp: (): { messages: any[] | null; expandedMessages: number[] } | null => {
    const stored = localStorage.getItem(FormStorageKeys.IRP);
    if (!stored) return null;
    try {
      return JSON.parse(stored);
    } catch {
      return null;
    }
  },
};

/**
 * Clear specific localStorage keys
 */
export const clearLocalStorage = {
  snmp: () => localStorage.removeItem(FormStorageKeys.SNMP),
  irp: () => localStorage.removeItem(FormStorageKeys.IRP),
  all: () => {
    localStorage.removeItem(FormStorageKeys.SNMP);
    localStorage.removeItem(FormStorageKeys.IRP);
  },
};

export default useFormStore;

