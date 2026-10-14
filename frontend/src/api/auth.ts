import type { User } from '../types/user';
import { apiFetch, apiPost } from './client';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export const login = (login_id: string, password: string) =>
  apiPost<LoginResponse>('/auth/login', { login_id, password });

export const fetchMe = () => apiFetch<{ user: User }>('/me').then((r) => r.user);
