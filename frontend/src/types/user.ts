export type Role = 'STUDENT' | 'WORKER' | 'SUPERVISOR' | 'SUPER_ADMIN';

export interface User {
  id: number;
  role: Role;
  login_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  locale: 'en' | 'hi' | 'mr';
  account_status: 'ACTIVE' | 'DISABLED' | 'LOCKED';
}
