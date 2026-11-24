import type { MyCredits } from '../types/credits';
import { apiFetch } from './client';

export const fetchMyCredits = () => apiFetch<MyCredits>('/me/credits');
