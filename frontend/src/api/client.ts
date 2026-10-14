const API_BASE = '/api/v1';
const STORAGE_KEY = 'hosteldesk.session';

export interface Session {
  accessToken: string;
  refreshToken: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null): void {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    return;
  }
}

let onSessionLost: () => void = () => {};
export function setSessionLostHandler(handler: () => void): void {
  onSessionLost = handler;
}

async function send(path: string, init: RequestInit, token?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function toError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => null);
  return new ApiError(
    res.status,
    body?.error?.code ?? 'UNKNOWN',
    body?.error?.message ?? 'Something went wrong. Please try again.',
  );
}

async function refreshAccessToken(session: Session): Promise<Session | null> {
  const res = await send('/auth/refresh', { method: 'POST' }, session.refreshToken);
  if (!res.ok) return null;
  const { access_token } = (await res.json()) as { access_token: string };
  const next = { ...session, accessToken: access_token };
  saveSession(next);
  return next;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let session = loadSession();
  let res = await send(path, init, session?.accessToken);

  if (res.status === 401 && session) {
    session = await refreshAccessToken(session);
    if (session) res = await send(path, init, session.accessToken);
    if (!session || res.status === 401) {
      saveSession(null);
      onSessionLost();
    }
  }

  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await send(path, { method: 'POST', body: JSON.stringify(body) });
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}
