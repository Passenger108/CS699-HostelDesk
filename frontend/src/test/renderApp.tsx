import { render } from '@testing-library/react';
import { App } from '../app/App';

export function mockApi(routes: Record<string, unknown>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = String(input).replace('/api/v1', '');
    if (!(path in routes)) return new Response('{}', { status: 404 });
    return new Response(JSON.stringify(routes[path]), { status: 200 });
  });
}

export function renderSignedIn(path: string) {
  localStorage.setItem('hosteldesk.session', JSON.stringify({ accessToken: 'a', refreshToken: 'r' }));
  window.history.pushState({}, '', path);
  return render(<App />);
}
