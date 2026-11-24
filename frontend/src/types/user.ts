export type Role = 'STUDENT' | 'WORKER' | 'SUPERVISOR' | 'SUPER_ADMIN';

export interface User {
  id: number;
  role: Role;
  login_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  locale: 'en' | 'hi' | 'mr';
  account_status: AccountStatus;
}

export type AccountStatus = 'ACTIVE' | 'DISABLED' | 'LOCKED';

export interface Account extends User {
  role_label: string;
  detail: string | null;
  created_at: string | null;
}

export interface NewAccount {
  role: Role;
  login_id: string;
  name: string;
  password: string;
  phone?: string;
  email?: string;
  roll_number?: string;
  room?: string;
  employee_id?: string;
  shift?: string;
}
