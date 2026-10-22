import { apiClient } from './client';
import { AuthResponse, User, UpdateProfilePayload, ChangePasswordPayload } from '../types';

export const authApi = {
  login: async (username: string, password: string): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login/', {
      username,
      password,
    });
    return response.data;
  },

  logout: async (refreshToken: string): Promise<void> => {
    await apiClient.post('/auth/logout/', { refresh: refreshToken });
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/profile/');
    return response.data;
  },

  updateProfile: async (payload: UpdateProfilePayload): Promise<User> => {
    const response = await apiClient.patch<User>('/auth/profile/', payload);
    return response.data;
  },

  changePassword: async (payload: ChangePasswordPayload): Promise<{ detail: string }> => {
    const response = await apiClient.post<{ detail: string }>('/auth/change-password/', payload);
    return response.data;
  },

  getUsers: async (): Promise<User[]> => {
    const response = await apiClient.get<{ results: User[] } | User[]>('/auth/users/');
    if ('results' in response.data) {
      return response.data.results;
    }
    return response.data;
  },

  createUser: async (data: Partial<User> & { password?: string }): Promise<User> => {
    const response = await apiClient.post<User>('/auth/users/', data);
    return response.data;
  },

  updateUser: async (id: number, data: Partial<User> & { password?: string }): Promise<User> => {
    const response = await apiClient.patch<User>(`/auth/users/${id}/`, data);
    return response.data;
  },

  deleteUser: async (id: number): Promise<void> => {
    await apiClient.delete(`/auth/users/${id}/`);
  },
};
