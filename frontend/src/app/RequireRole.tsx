import type { ReactNode } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { NotFoundPage } from '../pages/NotFoundPage';
import type { Role } from '../types/user';

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <NotFoundPage />;
  return <>{children}</>;
}
