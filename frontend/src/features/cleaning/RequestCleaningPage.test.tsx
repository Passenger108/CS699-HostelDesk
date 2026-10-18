import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockApi, renderSignedIn } from '../../test/renderApp';
import { creditsWith, studentMe, submittedRequest } from './fixtures';

function postedBody() {
  const call = vi
    .mocked(fetch)
    .mock.calls.find(([url, init]) => String(url).endsWith('/cleaning/requests') && init?.method === 'POST');
  return call ? JSON.parse(String(call[1]?.body)) : null;
}

describe('Request cleaning form', () => {
  it('shows the room and the credit that will be reserved', async () => {
    mockApi({
      '/me': studentMe,
      '/me/credits': creditsWith(2),
      '/cleaning/requests/active': { request: null },
    });
    renderSignedIn('/request');

    expect(await screen.findByRole('heading', { name: 'Request cleaning' })).toBeInTheDocument();
    expect(screen.getByText('A105')).toBeInTheDocument();
    expect(screen.getByText(/reserves 1 of your 2 available credits/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send request' })).toBeEnabled();
  });

  it('sends a time window request and goes home', async () => {
    const routes: Record<string, unknown> = {
      '/me': studentMe,
      '/me/credits': creditsWith(1),
      '/cleaning/requests/active': { request: null },
      '/cleaning/requests': { request: submittedRequest },
    };
    mockApi(routes);
    renderSignedIn('/request');

    await userEvent.click(await screen.findByLabelText('A time window today'));
    await userEvent.type(screen.getByLabelText('From'), '14:00');
    await userEvent.type(screen.getByLabelText('To'), '15:30');
    await userEvent.type(screen.getByLabelText(/Note for the worker/), 'Please clean the balcony');
    routes['/cleaning/requests/active'] = { request: submittedRequest };
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }));

    expect(await screen.findByRole('heading', { name: 'Home' })).toBeInTheDocument();
    expect(postedBody()).toMatchObject({
      availability_mode: 'TIME_WINDOW',
      window_start: '14:00',
      window_end: '15:30',
      priority: 'NORMAL',
      note: 'Please clean the balcony',
    });
    expect(postedBody().client_key).toBeTruthy();
  });

  it('blocks a normal request without credit but allows an urgent one', async () => {
    mockApi({
      '/me': studentMe,
      '/me/credits': creditsWith(0),
      '/cleaning/requests/active': { request: null },
      '/cleaning/requests': { request: { ...submittedRequest, priority: 'URGENT' } },
    });
    renderSignedIn('/request');

    expect(await screen.findByText(/no credit available/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled();

    await userEvent.click(screen.getByLabelText('Urgent'));
    expect(screen.getByText(/none will be used/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Why is it urgent?'), 'Water leak');
    await userEvent.click(screen.getByRole('button', { name: 'Send request' }));

    await waitFor(() =>
      expect(postedBody()).toMatchObject({ priority: 'URGENT', urgent_reason: 'Water leak' }),
    );
  });

  it('shows the server message when the request is refused', async () => {
    mockApi(
      {
        '/me': studentMe,
        '/me/credits': creditsWith(1),
        '/cleaning/requests/active': { request: null },
      },
      {
        '/cleaning/requests': [400, 'INVALID_AVAILABILITY', 'The time window cannot start in the past.'],
      },
    );
    renderSignedIn('/request');

    await userEvent.click(await screen.findByRole('button', { name: 'Send request' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The time window cannot start in the past.',
    );
  });

  it('does not show the form when a request is already active', async () => {
    mockApi({
      '/me': studentMe,
      '/me/credits': creditsWith(1),
      '/cleaning/requests/active': { request: submittedRequest },
    });
    renderSignedIn('/request');
    expect(await screen.findByText('You already have an active cleaning request.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send request' })).not.toBeInTheDocument();
  });

  it('is only for students', async () => {
    mockApi({ '/me': { user: { ...studentMe.user, role: 'WORKER' }, profile: null } });
    renderSignedIn('/request');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
});
