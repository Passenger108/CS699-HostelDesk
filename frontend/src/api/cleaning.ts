import type { CleaningRequest, NewCleaningRequest } from '../types/cleaning';
import { apiFetch } from './client';

type RequestResponse = { request: CleaningRequest };
type ActiveResponse = { request: CleaningRequest | null };

export const fetchActiveRequest = () => apiFetch<ActiveResponse>('/cleaning/requests/active');

export const submitCleaningRequest = (body: NewCleaningRequest) =>
  apiFetch<RequestResponse>('/cleaning/requests', { method: 'POST', body: JSON.stringify(body) });

export const cancelCleaningRequest = (id: number) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/cancel`, { method: 'POST' });
