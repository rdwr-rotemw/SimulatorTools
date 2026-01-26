import { User } from './auth';

export type { User } from './auth';

export interface UserCreate {
  username: string;
  password: string;
  roles: string[];
  workspace?: string;  // ADD THIS LINE - optional, only for super admin
}

export interface UserUpdate {
  password?: string;
  roles?: string[];
  is_active?: boolean;
  workspace?: string;  // ADD THIS LINE - optional, only super admin can update
}

export interface UserState {
  users: User[];
  selectedUser: User | null;
  isLoading: boolean;
  error: string | null;
  fetchUsers: () => Promise<void>;
  createUser: (data: UserCreate) => Promise<void>;
  updateUser: (userId: number, data: UserUpdate) => Promise<void>;
  deleteUser: (userId: number) => Promise<void>;
  clearError: () => void;
}
