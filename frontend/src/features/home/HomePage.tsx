import { SectionPage } from '../../pages/SectionPage';
import { useAuth } from '../auth/AuthContext';
import { CreditsCard } from '../credits/CreditsCard';

function StudentHome() {
  return (
    <div className="stack">
      <h1>Home</h1>
      <section className="card">
        <h2>Room cleaning</h2>
        <p className="muted">Requesting a cleaning is not available yet.</p>
      </section>
      <CreditsCard />
    </div>
  );
}

export function HomePage() {
  const { user } = useAuth();
  if (user?.role === 'STUDENT') return <StudentHome />;
  return <SectionPage />;
}
