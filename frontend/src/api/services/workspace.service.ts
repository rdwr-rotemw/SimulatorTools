import apiClient from '../client';

export interface WorkspaceInfo {
  name: string;
  full_path: string;
}

class WorkspaceService {
  async getWorkspaces(): Promise<WorkspaceInfo[]> {
    const response = await apiClient.get<{ workspaces: WorkspaceInfo[] }>('/workspaces');
    return response.data.workspaces;
  }
}

export const workspaceService = new WorkspaceService();
