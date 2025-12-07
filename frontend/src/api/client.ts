import axios, { AxiosInstance, AxiosError } from 'axios';

const DEFAULT_TIMEOUT = 30000;

const apiClient: AxiosInstance = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: Number(process.env.REACT_APP_API_TIMEOUT) || DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach Authorization header when token exists
apiClient.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem('token');
      if (token && config && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (e) {
      // Ignore localStorage errors (e.g., SSR or blocked access)
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 Unauthorized globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Don't handle 401 here - let auth store / route guards decide what to do.
    return Promise.reject(error);
  }
);

export default apiClient;
