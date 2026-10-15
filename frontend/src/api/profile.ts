import type { Profile } from '../types/profile';
import type { User } from '../types/user';
import { apiFetch } from './client';

export const fetchMyProfile = () => apiFetch<{ user: User; profile: Profile }>('/me');
