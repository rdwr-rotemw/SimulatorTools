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

// Ensure retry is disabled (no axios-retry usage expected in this project). Some retry wrappers/libraries look
// for `retries` or `retry` on the axios instance defaults — set them to 0 explicitly to be safe.
(apiClient.defaults as any).retries = 0;
(apiClient.defaults as any).retry = 0;

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

// Response interceptor: handle 401 Unauthorized globally and surface backend error messages
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

    // Ensure backend error message gets surfaced so callers and UI can show the exact message from the server.
    try {
      const respData: any = (error as any).response?.data;
      if (respData) {
        let backendMessage: string | undefined;
        if (typeof respData === 'string') backendMessage = respData;
        else if (respData.detail) backendMessage = respData.detail;
        else if (respData.message) backendMessage = respData.message;
        else if (respData.error) backendMessage = respData.error;
        else backendMessage = JSON.stringify(respData);
        if (backendMessage) {
          // mutate the error.message so the UI that displays `error.message` will show backend text.
          (error as any).message = backendMessage;
        }
      }
    } catch (e) {
      // swallow any problems extracting the backend message — don't block the original error flow
    }

    // Always pass the original AxiosError through so callers still have access to response/status/etc.
    return Promise.reject(error);
  }
);

export default apiClient;
