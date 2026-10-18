import { SectionPage } from '../../pages/SectionPage';
import { useAuth } from '../auth/AuthContext';
import { ActiveRequestCard } from '../cleaning/ActiveRequestCard';
import { CreditsCard } from '../credits/CreditsCard';

function StudentHome() {
  return (
    <div className="stack">
      <h1>Home</h1>
      <ActiveRequestCard />
      <CreditsCard />
    </div>
  );
}

export function HomePage() {
  const { user } = useAuth();
  if (user?.role === 'STUDENT') return <StudentHome />;
  return <SectionPage />;
}
