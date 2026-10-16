import { screen, within } from '@testing-library/react';
import { mockApi, renderSignedIn } from '../../test/renderApp';

const student = {
  id: 1,
  role: 'STUDENT',
  login_id: 'demo.student',
  name: 'Demo Student',
  phone: null,
  email: null,
  locale: 'en',
  account_status: 'ACTIVE',
};

const credits = {
  balance: {
    available: 2,
    standard_available: 1,
    goodwill_available: 1,
    reserved: 1,
    consumed: 3,
    cap: 3,
    next_grant_at: '2026-10-25T18:30:00+00:00',
  },
  history: [
    {
      id: 3,
      entry_type: 'GOODWILL_GRANT',
      credit_type: 'GOODWILL',
      quantity: 1,
      reason: 'Valid complaint',
      request_id: null,
      created_at: '2026-10-21T06:00:00+00:00',
      expires_at: '2026-10-25T18:30:00+00:00',
      grant_week: null,
    },
    {
      id: 2,
      entry_type: 'RESERVE',
      credit_type: 'STANDARD',
      quantity: 1,
      reason: 'Reserved for a cleaning request',
      request_id: 9,
      created_at: '2026-10-20T06:00:00+00:00',
      expires_at: null,
      grant_week: null,
    },
    {
      id: 1,
      entry_type: 'WEEKLY_GRANT',
      credit_type: 'STANDARD',
      quantity: 1,
      reason: 'Weekly credit',
      request_id: null,
      created_at: '2026-10-18T18:30:00+00:00',
      expires_at: null,
      grant_week: '2026-10-19',
    },
  ],
};

function stat(label: string) {
  return screen.getByText(label).previousSibling?.textContent;
}

describe('Credits', () => {
  it('shows balances and history on the credits page', async () => {
    mockApi({ '/me': { user: student, profile: null }, '/me/credits': credits });
    renderSignedIn('/credits');

    expect(await screen.findByRole('heading', { name: 'Credits' })).toBeInTheDocument();
    expect(stat('Available')).toBe('2');
    expect(stat('Reserved')).toBe('1');
    expect(stat('Used')).toBe('3');
    expect(stat('Goodwill')).toBe('1');
    expect(screen.getByText(/carry over, up to 3/)).toBeInTheDocument();

    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining('Goodwill credit from the supervisor'),
      expect.stringContaining('Reserved for a cleaning request'),
      expect.stringContaining('Weekly credit added'),
    ]);
    expect(rows[0]).toHaveTextContent('expires 26 Oct 2026');
    expect(rows[2]).toHaveTextContent('Week of 19 Oct 2026');
  });

  it('shows an empty history', async () => {
    mockApi({
      '/me': { user: student, profile: null },
      '/me/credits': { balance: { ...credits.balance, available: 0 }, history: [] },
    });
    renderSignedIn('/credits');
    expect(await screen.findByText('No credit activity yet.')).toBeInTheDocument();
  });

  it('shows a credits card on the student home page', async () => {
    mockApi({ '/me': { user: student, profile: null }, '/me/credits': credits });
    renderSignedIn('/');
    expect(await screen.findByRole('heading', { name: 'Cleaning credits' })).toBeInTheDocument();
    expect(await screen.findByText('available')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See credit history' })).toHaveAttribute('href', '/credits');
  });

  it('is not available to other roles', async () => {
    mockApi({ '/me': { user: { ...student, role: 'WORKER' }, profile: null } });
    renderSignedIn('/credits');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
});
