import { Route, Routes } from 'react-router-dom';
import { LoginPage } from '../features/auth/LoginPage';
import { HostelStructurePage } from '../features/hostel/HostelStructurePage';
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
          <Route path="/settings" element={<ProfilePage />} />
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
