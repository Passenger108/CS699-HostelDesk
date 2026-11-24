import { ApiError } from '../api/client';

export function ErrorMessage({ error, fallback }: { error: unknown; fallback: string }) {
  const message = error instanceof ApiError ? error.message : fallback;
  return (
    <p className="error" role="alert">
      {message}
    </p>
  );
}
