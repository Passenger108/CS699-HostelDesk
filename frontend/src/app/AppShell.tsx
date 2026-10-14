import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import { NAVIGATION, ROLE_LABELS } from './navigation';

export function AppShell() {
  const { user, signOut } = useAuth();
  if (!user) return null;

  return (
    <div className="shell">
      <header className="shell__header">
        <span className="shell__brand">HostelDesk</span>
        <span className="chip">{ROLE_LABELS[user.role]}</span>
        <span className="shell__user">{user.name}</span>
        <button type="button" className="btn btn--ghost" onClick={signOut}>
          Sign out
        </button>
      </header>
      <nav className="shell__nav" aria-label="Primary">
        {NAVIGATION[user.role].map((item) => (
          <NavLink key={item.path} to={item.path} end={item.path === '/'}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}
