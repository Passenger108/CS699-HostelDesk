import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ErrorMessage } from "../components/ErrorMessage";
import { useAuth } from "../features/auth/AuthContext";

export function RequireAuth() {
  const { user, isLoading, loadError, retry } = useAuth();
  const location = useLocation();

  if (isLoading) return <p className="page-loading">Loading…</p>;
  if (loadError) {
    return (
      <main className="login">
        <section className="card login__card">
          <h1 className="login__title">HostelDesk</h1>
          <ErrorMessage
            error={loadError}
            fallback="Could not reach HostelDesk. Check your connection."
          />
          <button type="button" className="btn btn--primary" onClick={retry}>
            Try again
          </button>
        </section>
      </main>
    );
  }
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
