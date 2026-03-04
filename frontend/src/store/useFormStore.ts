import { create } from 'zustand';

/**
 * Session identifier for tracking user and CC context
 */
interface SessionInfo {
  cc: string | null;
  userId: string | null;
}

/**
 * Store interface — session tracking only (form state persisted in MongoDB)
 */
interface FormStore {
  session: SessionInfo;

  // Session management methods
  setCurrentSession: (cc: string, userId?: string) => void;
  isSessionValid: (cc: string, userId?: string) => boolean;
  clearAllFormState: () => void;
}

/**
 * Zustand store for session tracking only.
 * Form state (IRP messages, SNMP traps) is now persisted in MongoDB
 * via formStateService — no more localStorage / persist middleware.
 */
const useFormStore = create<FormStore>()((set, get) => ({
  session: {
    cc: null,
    userId: null,
  },

  setCurrentSession: (cc: string, userId?: string) => {
    set({
      session: {
        cc,
        userId: userId || null,
      },
    });
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
    });
  },
}));

export default useFormStore;
