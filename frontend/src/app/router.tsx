import { Route, Routes } from 'react-router-dom';
import { LoginPage } from '../features/auth/LoginPage';
import { SectionPage } from '../pages/SectionPage';
import { AppShell } from './AppShell';
import { RequireAuth } from './RequireAuth';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="*" element={<SectionPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
