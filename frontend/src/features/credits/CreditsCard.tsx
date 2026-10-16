import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchMyCredits } from '../../api/credits';
import { ErrorMessage } from '../../components/ErrorMessage';
import { formatDateTime } from '../../utils/format';

export function CreditsCard() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['credits'],
    queryFn: fetchMyCredits,
  });

  return (
    <section className="card">
      <h2>Cleaning credits</h2>
      {isPending && <p className="muted">Loading…</p>}
      {isError && <ErrorMessage error={error} fallback="Could not load your credits." />}
      {data && (
        <>
          <p className="credits-card__count">
            <strong>{data.balance.available}</strong> available
            {data.balance.reserved > 0 && <span className="muted"> · {data.balance.reserved} reserved</span>}
          </p>
          <p className="muted">Next weekly credit: {formatDateTime(data.balance.next_grant_at)}</p>
          <Link to="/credits">See credit history</Link>
        </>
      )}
    </section>
  );
}
