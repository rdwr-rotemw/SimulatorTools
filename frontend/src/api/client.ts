// IMPORTANT: Frontend API call convention
// - Do NOT prefix request paths with a leading '/api' (for example, avoid apiClient.post('/api/xyz')).
// - The axios instance `apiClient` is configured with a baseURL (from REACT_APP_API_BASE_URL) which may already
//   include the '/api' segment when needed. Adding '/api' again at call sites results in duplicated paths
//   like '/api/api/...' and causes requests to fail. Always supply paths relative to the configured baseURL,
//   e.g. apiClient.post('/reporter/snmp/import-from-pcap', formData).

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
    // Handle 401 Token Expired - redirect to login
    if (error.response?.status === 401) {
      const errorData = error.response.data as any;
      if (errorData?.detail === 'Token has expired') {
        // Clear token and redirect to login
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
