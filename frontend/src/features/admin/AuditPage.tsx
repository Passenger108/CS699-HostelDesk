import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchAudit } from "../../api/admin";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { AuditEntry, AuditFilters } from "../../types/audit";
import { formatDateTime } from "../../utils/format";

type TextFilter = Exclude<keyof AuditFilters, "action" | "page">;

const TEXT_FILTERS: [TextFilter, string, string][] = [
  ["actor", "Who (name or login ID)", "text"],
  ["request", "Request number", "number"],
  ["date_from", "From", "date"],
  ["date_to", "To", "date"],
];

function readable(action: string) {
  const words = action.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function today() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(
    new Date(),
  );
}

function Target({ entry }: { entry: AuditEntry }) {
  if (entry.entity_type === "cleaning_request" && entry.entity_id)
    return (
      <Link
        to={`/requests/${entry.entity_id}`}
        className="btn btn--ghost btn--small"
      >
        {entry.entity_label}
      </Link>
    );
  return <>{entry.entity_label}</>;
}

export function AuditPage() {
  const [draft, setDraft] = useState<AuditFilters>({});
  const [filters, setFilters] = useState<AuditFilters>({ page: 1 });
  const { data, isPending, error, isFetching } = useQuery({
    queryKey: ["admin", "audit", filters],
    queryFn: () => fetchAudit(filters),
    placeholderData: keepPreviousData,
  });
  const page = filters.page ?? 1;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <section className="stack">
      <h1>Audit log</h1>
      <form
        className="card stack"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters({ ...draft, page: 1 });
        }}
      >
        <div className="form-grid">
          <label className="text-field">
            Action
            <select
              value={draft.action ?? ""}
              onChange={(e) => setDraft({ ...draft, action: e.target.value })}
            >
              <option value="">All actions</option>
              {data?.actions.map((action) => (
                <option key={action} value={action}>
                  {readable(action)}
                </option>
              ))}
            </select>
          </label>
          {TEXT_FILTERS.map(([key, label, type]) => (
            <label key={key} className="text-field">
              {label}
              <input
                type={type}
                min={type === "number" ? 1 : data?.first_day}
                max={type === "date" ? today() : undefined}
                value={draft[key] ?? ""}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
              />
            </label>
          ))}
        </div>
        <div className="choice-row">
          <button type="submit" className="btn btn--primary">
            Search
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setDraft({});
              setFilters({ page: 1 });
            }}
          >
            Clear
          </button>
        </div>
      </form>
      {isPending && <p className="page-loading">Loading…</p>}
      {error && (
        <ErrorMessage error={error} fallback="Could not load the audit log." />
      )}
      {data && data.total === 0 && (
        <p className="card muted">Nothing matches these filters.</p>
      )}
      {data && data.total > 0 && (
        <div className="card table-wrap" aria-busy={isFetching}>
          <p className="muted">{data.total} entries, newest first.</p>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Who</th>
                <th scope="col">Action</th>
                <th scope="col">On</th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{formatDateTime(entry.created_at)}</td>
                  <td>{entry.actor?.name ?? "System"}</td>
                  <td>{readable(entry.action)}</td>
                  <td>
                    <Target entry={entry} />
                  </td>
                  <td>{entry.reason ?? "—"}</td>
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
            onClick={() => setFilters({ ...filters, page: page - 1 })}
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
            onClick={() => setFilters({ ...filters, page: page + 1 })}
          >
            Older
          </button>
        </nav>
      )}
    </section>
  );
}
