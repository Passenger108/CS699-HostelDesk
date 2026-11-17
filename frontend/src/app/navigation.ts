import type { Role } from '../types/user';

export interface NavItem {
  path: string;
  label: string;
}

export const NAVIGATION: Record<Role, NavItem[]> = {
  STUDENT: [
    { path: '/', label: 'Home' },
    { path: '/history', label: 'History' },
    { path: '/credits', label: 'Credits' },
    { path: '/settings', label: 'Profile' },
  ],
  WORKER: [
    { path: '/', label: 'Home' },
    { path: '/settings', label: 'Profile' },
  ],
  SUPERVISOR: [
    { path: '/', label: 'Operations' },
    { path: '/workers', label: 'Workers' },
    { path: '/settings', label: 'Profile' },
  ],
  SUPER_ADMIN: [
    { path: '/', label: 'Operations' },
    { path: '/people', label: 'People' },
    { path: '/workers', label: 'Workers' },
    { path: '/structure', label: 'Hostel Structure' },
    { path: '/settings', label: 'Profile' },
  ],
};

export const ROLE_LABELS: Record<Role, string> = {
  STUDENT: 'Student',
  WORKER: 'Worker',
  SUPERVISOR: 'Supervisor',
  SUPER_ADMIN: 'Super Admin',
};
