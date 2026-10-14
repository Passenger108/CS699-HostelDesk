import { useLocation } from 'react-router-dom';
import { NAVIGATION } from '../app/navigation';
import { useAuth } from '../features/auth/AuthContext';
import { NotFoundPage } from './NotFoundPage';

export function SectionPage() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const item = user && NAVIGATION[user.role].find((n) => n.path === pathname);
  if (!item) return <NotFoundPage />;

  return (
    <section className="card">
      <h1>{item.label}</h1>
      <p className="muted">This screen is not built yet.</p>
    </section>
  );
}
