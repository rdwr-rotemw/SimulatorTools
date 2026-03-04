import apiClient from '../client';

export interface CCFavorite {
  cc_ip: string;
  username: string;
  password: string;
  created_at: string;
}

export const ccFavoritesService = {
  async list(): Promise<CCFavorite[]> {
    const response = await apiClient.get<CCFavorite[]>('/cc/favorites');
    return response.data;
  },

  async save(cc_ip: string, username: string, password: string): Promise<void> {
    await apiClient.post('/cc/favorites', { cc_ip, username, password });
  },

  async remove(cc_ip: string): Promise<void> {
    await apiClient.delete(`/cc/favorites/${cc_ip}`);
  },
};
