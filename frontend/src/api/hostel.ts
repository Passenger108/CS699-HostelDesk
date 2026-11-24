import type { HostelStructure } from '../types/hostel';
import { apiFetch } from './client';

export const fetchHostelStructure = () =>
  apiFetch<{ hostel: HostelStructure }>('/hostel/structure').then((r) => r.hostel);
