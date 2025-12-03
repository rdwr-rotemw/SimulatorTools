import { create } from 'zustand';
import { userService } from '../api/services/user.service';
import { UserState, UserCreate, UserUpdate } from '../types/user.types';

export const useUserStore = create<UserState>((set) => ({
  users: [],
  selectedUser: null,
  isLoading: false,
  error: null,

  fetchUsers: async () => {
    set({ isLoading: true, error: null });
    try {
      const users = await userService.getUsers();
      set({ users, isLoading: false });
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to fetch users';
      set({ error: message, isLoading: false });
    }
  },

  createUser: async (data: UserCreate) => {
    set({ isLoading: true, error: null });
    try {
      const created = await userService.createUser(data);
      set((state) => ({ users: [...state.users, created], isLoading: false }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to create user';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  updateUser: async (userId: number, data: UserUpdate) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await userService.updateUser(userId, data);
      set((state) => ({
        users: state.users.map((u) => (u.user_id === userId ? updated : u)),
        isLoading: false,
      }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to update user';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  deleteUser: async (userId: number) => {
    set({ isLoading: true, error: null });
    try {
      await userService.deleteUser(userId);
      set((state) => ({ users: state.users.filter((u) => u.user_id !== userId), isLoading: false }));
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to delete user';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));

export default useUserStore;
