import apiClient from '../client';
import { LoginRequest, LoginResponse } from '../../types/auth';

export const authService = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const payload = { username, password } as LoginRequest;
    const response = await apiClient.post<LoginResponse>('/login', payload);
    return response.data;
  },

  getToken: (): string | null => {
    try {
      return localStorage.getItem('token');
    } catch (e) {
      return null;
    }
  },

  setToken: (token: string): void => {
    try {
      localStorage.setItem('token', token);
    } catch (e) {
      // ignore storage errors
    }
  },

  clearToken: (): void => {
    try {
      localStorage.removeItem('token');
    } catch (e) {
      // ignore
    }
  },

  isAuthenticated: (): boolean => {
    return !!authService.getToken();
  },
};

export default authService;

