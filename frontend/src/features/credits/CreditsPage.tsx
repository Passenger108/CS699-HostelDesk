import { useQuery } from '@tanstack/react-query';
import { fetchMyCredits } from '../../api/credits';
import { ErrorMessage } from '../../components/ErrorMessage';
import { formatDateTime, formatDay } from '../../utils/format';
import { ENTRY_LABELS, ENTRY_SIGN } from './labels';

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}

export function CreditsPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['credits'],
    queryFn: fetchMyCredits,
  });

  if (isPending) return <p className="page-loading">Loading…</p>;
  if (isError) return <ErrorMessage error={error} fallback="Could not load your credits." />;

  const { balance, history } = data;
  return (
    <div className="stack">
      <h1>Credits</h1>
      <section className="card">
        <div className="stats">
          <Stat label="Available" value={balance.available} />
          <Stat label="Reserved" value={balance.reserved} />
          <Stat label="Used" value={balance.consumed} />
          <Stat label="Goodwill" value={balance.goodwill_available} />
        </div>
        <p className="muted">
          You get one credit every Monday. Unused credits carry over, up to {balance.cap}. Next
          weekly credit: {formatDateTime(balance.next_grant_at)}.
        </p>
      </section>

      <section className="card">
        <h2>History</h2>
        {history.length === 0 ? (
          <p className="muted">No credit activity yet.</p>
        ) : (
          <ul className="ledger">
            {history.map((entry) => (
              <li key={entry.id} className="ledger__row">
                <span className="ledger__sign">{ENTRY_SIGN[entry.entry_type]}</span>
                <span>
                  <span className="ledger__label">{ENTRY_LABELS[entry.entry_type]}</span>
                  <span className="muted ledger__meta">
                    {entry.grant_week
                      ? `Week of ${formatDay(entry.grant_week)}`
                      : formatDateTime(entry.created_at)}
                    {entry.expires_at && ` · expires ${formatDateTime(entry.expires_at)}`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
