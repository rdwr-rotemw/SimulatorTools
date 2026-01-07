// Authentication-related TypeScript interfaces

// Request payload for login
export interface LoginRequest {
  username: string;
  password: string;
}

// User model returned from the backend
// Note: `updated_at` can be null when the record was never updated.
export interface User {
  user_id: number;
  username: string;
  is_active: boolean;
  roles: string[];
  created_at: string; // ISO8601 timestamp
  updated_at: string | null; // ISO8601 timestamp or null
}

// Response from the login endpoint
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Local auth state used in stores/hooks
export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Attempts to login and resolves when complete. Should set token/user on success.
  login: (username: string, password: string) => Promise<boolean>;

  // Clears auth state and removes token
  logout: () => void;

  // Clears the current error message
  clearError: () => void;

  // Restores auth state from persisted storage
  checkAuth: () => void;

  // Initializes activity tracking for the authenticated user
  initializeActivityTracking: () => void;
}
