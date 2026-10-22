import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchRequests } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import { formatDateTime } from "../../utils/format";
import { PRIORITY_LABELS } from "./labels";
import { StatusChip } from "./StatusChip";

const PAGE_SIZE = 10;

export function HistoryPage() {
  const [page, setPage] = useState(1);
  const { data, isPending, error } = useQuery({
    queryKey: ["cleaning", "list", "mine", page],
    queryFn: () => fetchRequests({ page, per_page: PAGE_SIZE }),
  });

  if (isPending) return <p className="page-loading">Loading…</p>;
  if (error)
    return (
      <ErrorMessage error={error} fallback="Could not load your history." />
    );

  const pages = Math.max(1, Math.ceil(data.total / data.per_page));

  return (
    <section className="stack">
      <h1>History</h1>
      {data.total === 0 ? (
        <p className="card muted">You have not asked for cleaning yet.</p>
      ) : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Requested</th>
                <th scope="col">Status</th>
                <th scope="col">Room</th>
                <th scope="col">Worker</th>
                <th scope="col">Closed</th>
              </tr>
            </thead>
            <tbody>
              {data.requests.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link to={`/requests/${row.id}`}>
                      {formatDateTime(row.created_at)}
                    </Link>
                    {row.priority !== "NORMAL" && (
                      <span className="chip">
                        {PRIORITY_LABELS[row.priority]}
                      </span>
                    )}
                  </td>
                  <td>
                    <StatusChip request={row} />
                  </td>
                  <td>{row.room.number}</td>
                  <td>{row.assigned_worker?.name ?? "—"}</td>
                  <td>{row.closed_at ? formatDateTime(row.closed_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <nav className="pager" aria-label="Pages">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Newer
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            Older
          </button>
        </nav>
      )}
    </section>
  );
}
