import { create } from 'zustand';
import authService from '../api/services/auth.service';
import { AuthState } from '../types/auth';
import useFormStore from './useFormStore';
import activityTracker from '../utils/activityTracker';
import useCCStore from './ccStore';
import useLoopStore from './useLoopStore';

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (username: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const res = await authService.login(username, password);
      // Persist token and update store
      authService.setToken(res.access_token);
      // Save user to localStorage for session restore
      localStorage.setItem('user', JSON.stringify(res.user));
      set({ user: res.user, token: res.access_token, isAuthenticated: true, isLoading: false });
      // Track activity and start inactivity monitoring
      activityTracker.updateActivity();
      get().initializeActivityTracking();
      return true;
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Login failed';
      set({ isLoading: false, error: message });
      // Don't re-throw the error - it's already stored in state and shown via UI
      return false;
    }
  },

  logout: async () => {
    // Cancel any active loops before logout
    const loopStore = useLoopStore.getState();
    if (loopStore.snmp.isLooping) {
      loopStore.clearSnmpLoop();
    }
    if (loopStore.irp.isLooping) {
      loopStore.clearIrpLoop();
    }

    try {
      // First, logout from CC if there's an active CC session
      const ccStore = useCCStore.getState();
      if (ccStore.currentCC) {
        try {
          await ccStore.logout(ccStore.currentCC);
          ccStore.clearState();
        } catch (error) {
          // Log but don't block system logout if CC logout fails
          console.error('Failed to logout from CC:', error);
        }
      }
    } catch (error) {
      console.error('CC logout error:', error);
    }

    // Then proceed with normal system logout
    activityTracker.stopTracking();
    activityTracker.clearActivity();
    authService.clearToken();
    // Remove persisted user on logout
    localStorage.removeItem('user');
    // Clear form state on logout
    useFormStore.getState().clearAllFormState();
    set({ user: null, token: null, isAuthenticated: false, error: null });
  },

  clearError: () => set({ error: null }),

  checkAuth: () => {
    const token = authService.getToken();
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        // Check if user has been inactive for too long
        if (activityTracker.isInactive()) {
          // Session expired due to inactivity
          authService.clearToken();
          localStorage.removeItem('user');
          activityTracker.clearActivity();
          set({ user: null, token: null, isAuthenticated: false, error: null });
        } else {
          // Session is still valid, restore and start tracking
          set({ token, user, isAuthenticated: true });
          get().initializeActivityTracking();
        }
      } catch (error) {
        authService.clearToken();
        localStorage.removeItem('user');
      }
    }
  },

  initializeActivityTracking: () => {
    const { isAuthenticated, logout } = get();
    if (isAuthenticated) {
      activityTracker.startTracking(async () => {
        // Check if any loop is active before logging out due to inactivity
        const loopStore = useLoopStore.getState();
        if (loopStore.snmp.isLooping || loopStore.irp.isLooping) {
          // Skip logout while loop is running, continue tracking
          console.log('Inactivity timeout skipped: Loop is active');
          return;
        }
        // User inactive for 15 minutes and no loop running
        alert('Session expired due to inactivity');
        await logout();
      });
    }
  },
}));

export default useAuthStore;
