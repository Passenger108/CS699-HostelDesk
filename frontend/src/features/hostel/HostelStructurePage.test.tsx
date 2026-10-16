import { screen } from '@testing-library/react';
import { mockApi, renderSignedIn } from '../../test/renderApp';

const user = (role: string) => ({
  id: 4,
  role,
  login_id: 'demo.admin',
  name: 'Demo Admin',
  phone: null,
  email: null,
  locale: 'en',
  account_status: 'ACTIVE',
});

const hostel = {
  id: 1,
  code: 'H4',
  name: 'Hostel 4',
  floors: [
    {
      id: 1,
      number: 0,
      label: 'Ground floor',
      wings: [],
      facilities: [
        { id: 1, kind: 'GROUND_FACILITY', floor: 0, wing: null, facility_name: 'Reception desk', label: 'Ground floor, Reception desk' },
      ],
    },
    {
      id: 2,
      number: 1,
      label: 'Floor 1',
      wings: [
        { id: 1, code: 'A', rooms: [{ id: 1, number: 'A101' }, { id: 2, number: 'A102' }] },
        { id: 2, code: 'B', rooms: [{ id: 3, number: 'B101' }] },
      ],
      facilities: [],
    },
  ],
};

describe('Hostel structure page', () => {
  it('shows floors, wings and rooms to the super admin', async () => {
    mockApi({ '/me': { user: user('SUPER_ADMIN'), profile: null }, '/hostel/structure': { hostel } });
    renderSignedIn('/structure');

    expect(await screen.findByText('Hostel 4 structure')).toBeInTheDocument();
    expect(screen.getByText('1 residential floors · 3 rooms · read only')).toBeInTheDocument();
    expect(screen.getByText('2 wings · 3 rooms')).toBeInTheDocument();
    expect(screen.getByText('Reception desk')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Floor 1, Wing A rooms' })).toHaveTextContent('A101A102');
  });

  it('shows the server message when the structure is not set up', async () => {
    mockApi(
      { '/me': { user: user('SUPER_ADMIN'), profile: null } },
      {
        '/hostel/structure': [
          404,
          'HOSTEL_NOT_FOUND',
          'The hostel structure has not been set up yet.',
        ],
      },
    );
    renderSignedIn('/structure');
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The hostel structure has not been set up yet.',
    );
  });

  it('is not available to other roles', async () => {
    mockApi({ '/me': { user: user('STUDENT'), profile: null } });
    renderSignedIn('/structure');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
});
