import { screen } from '@testing-library/react';
import { mockApi, renderSignedIn } from '../../test/renderApp';

const baseUser = {
  phone: null,
  email: null,
  locale: 'en',
  account_status: 'ACTIVE',
};

describe('Profile page', () => {
  it('shows the student room, floor and wing', async () => {
    mockApi({
      '/me': {
        user: { ...baseUser, id: 1, role: 'STUDENT', login_id: 'demo.student', name: 'Demo Student' },
        profile: {
          roll_number: 'DEMO24B001',
          room: { id: 5, number: 'A105', floor: 1, floor_label: 'Floor 1', wing: 'A' },
        },
      },
    });
    renderSignedIn('/settings');

    expect(await screen.findByText('A105')).toBeInTheDocument();
    expect(screen.getByText('Floor 1')).toBeInTheDocument();
    expect(screen.getByText('DEMO24B001')).toBeInTheDocument();
    expect(screen.getByText('demo.student')).toBeInTheDocument();
  });

  it('shows worker details with an unset location', async () => {
    mockApi({
      '/me': {
        user: { ...baseUser, id: 2, role: 'WORKER', login_id: 'demo.worker', name: 'Demo Worker' },
        profile: {
          employee_id: 'DEMO-W01',
          shift: 'Morning',
          availability: 'AVAILABLE',
          last_location: null,
          location_updated_at: null,
        },
      },
    });
    renderSignedIn('/settings');

    expect(await screen.findByText('DEMO-W01')).toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();
    expect(screen.getByText('Not set yet')).toBeInTheDocument();
  });
});
