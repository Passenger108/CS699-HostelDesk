import { useQuery } from '@tanstack/react-query';
import { fetchMyProfile } from '../../api/profile';
import type { StudentProfile, WorkerProfile } from '../../types/profile';
import type { User } from '../../types/user';

const AVAILABILITY_LABELS: Record<WorkerProfile['availability'], string> = {
  AVAILABLE: 'Available',
  BUSY: 'Busy',
  OFF_DUTY: 'Off duty',
};

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{value || '—'}</dd>
    </div>
  );
}

function StudentDetails({ profile }: { profile: StudentProfile }) {
  return (
    <section className="card">
      <h2>Room</h2>
      {profile.room ? (
        <dl className="field-grid">
          <Field label="Room" value={profile.room.number} />
          <Field label="Floor" value={profile.room.floor_label} />
          <Field label="Wing" value={profile.room.wing} />
          <Field label="Roll number" value={profile.roll_number} />
        </dl>
      ) : (
        <p className="muted">No room is assigned yet. Contact the hostel office.</p>
      )}
    </section>
  );
}

function WorkerDetails({ profile }: { profile: WorkerProfile }) {
  return (
    <section className="card">
      <h2>Work</h2>
      <dl className="field-grid">
        <Field label="Employee ID" value={profile.employee_id} />
        <Field label="Shift" value={profile.shift} />
        <Field label="Availability" value={AVAILABILITY_LABELS[profile.availability]} />
        <Field label="Last location" value={profile.last_location?.label ?? 'Not set yet'} />
      </dl>
    </section>
  );
}

function AccountDetails({ user }: { user: User }) {
  return (
    <section className="card">
      <h2>Account</h2>
      <dl className="field-grid">
        <Field label="Name" value={user.name} />
        <Field label="Login ID" value={user.login_id} />
        <Field label="Email" value={user.email} />
        <Field label="Phone" value={user.phone} />
      </dl>
    </section>
  );
}

export function ProfilePage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['me', 'profile'],
    queryFn: fetchMyProfile,
  });

  if (isPending) return <p className="page-loading">Loading…</p>;
  if (isError) return <p className="error" role="alert">Could not load your profile.</p>;

  const { user, profile } = data;
  return (
    <div className="stack">
      <h1>Profile</h1>
      {user.role === 'STUDENT' && profile && <StudentDetails profile={profile as StudentProfile} />}
      {user.role === 'WORKER' && profile && <WorkerDetails profile={profile as WorkerProfile} />}
      <AccountDetails user={user} />
    </div>
  );
}
