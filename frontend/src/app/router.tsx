import { Route, Routes } from 'react-router-dom';
import { LoginPage } from '../features/auth/LoginPage';
import { RequestCleaningPage } from '../features/cleaning/RequestCleaningPage';
import { CreditsPage } from '../features/credits/CreditsPage';
import { HostelStructurePage } from '../features/hostel/HostelStructurePage';
import { HomePage } from '../features/home/HomePage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { SectionPage } from '../pages/SectionPage';
import { AppShell } from './AppShell';
import { RequireAuth } from './RequireAuth';
import { RequireRole } from './RequireRole';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/settings" element={<ProfilePage />} />
          <Route
            path="/credits"
            element={
              <RequireRole roles={['STUDENT']}>
                <CreditsPage />
              </RequireRole>
            }
          />
          <Route
            path="/request"
            element={
              <RequireRole roles={['STUDENT']}>
                <RequestCleaningPage />
              </RequireRole>
            }
          />
          <Route
            path="/structure"
            element={
              <RequireRole roles={['SUPER_ADMIN']}>
                <HostelStructurePage />
              </RequireRole>
            }
          />
          <Route path="*" element={<SectionPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
