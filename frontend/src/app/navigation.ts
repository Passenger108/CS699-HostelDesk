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
    { path: '/settings', label: 'Profile & Settings' },
  ],
  WORKER: [
    { path: '/', label: 'Home' },
    { path: '/queue', label: 'Queue' },
    { path: '/history', label: 'History' },
    { path: '/scorecard', label: 'Scorecard' },
    { path: '/settings', label: 'Settings' },
  ],
  SUPERVISOR: [
    { path: '/', label: 'Operations' },
    { path: '/workers', label: 'Workers' },
    { path: '/reports', label: 'Reports' },
    { path: '/settings', label: 'Settings' },
  ],
  SUPER_ADMIN: [
    { path: '/', label: 'Dashboard' },
    { path: '/people', label: 'People' },
    { path: '/structure', label: 'Hostel Structure' },
    { path: '/reports', label: 'Reports' },
    { path: '/settings', label: 'Settings' },
    { path: '/audit', label: 'Audit' },
  ],
};

export const ROLE_LABELS: Record<Role, string> = {
  STUDENT: 'Student',
  WORKER: 'Worker',
  SUPERVISOR: 'Supervisor',
  SUPER_ADMIN: 'Super Admin',
};
