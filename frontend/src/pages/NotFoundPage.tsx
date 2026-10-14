import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section className="card">
      <h1>Page not found</h1>
      <p className="muted">This page does not exist or is not available for your role.</p>
      <Link to="/">Go home</Link>
    </section>
  );
}
