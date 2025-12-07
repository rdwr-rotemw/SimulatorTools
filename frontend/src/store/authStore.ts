import { create } from 'zustand';
import authService from '../api/services/auth.service';
import { AuthState } from '../types/auth';

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
      return true;
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Login failed';
      set({ isLoading: false, error: message });
      // Don't re-throw the error - it's already stored in state and shown via UI
      return false;
    }
  },

  logout: () => {
    authService.clearToken();
    // Remove persisted user on logout
    localStorage.removeItem('user');
    set({ user: null, token: null, isAuthenticated: false, error: null });
  },

  clearError: () => set({ error: null }),

  checkAuth: () => {
    const token = authService.getToken();
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        set({ token, user, isAuthenticated: true });
      } catch (error) {
        authService.clearToken();
        localStorage.removeItem('user');
      }
    }
  },
}));

export default useAuthStore;
