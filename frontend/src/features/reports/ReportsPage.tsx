import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { downloadReport, fetchReport } from "../../api/reports";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { Column, ReportRow, ReportTable } from "../../types/report";

const TABLES: [ReportTable, string][] = [
  ["days", "Day by day"],
  ["workers", "By worker"],
];

function thisMonth() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
  }).format(new Date());
}

function Table({ columns, rows }: { columns: Column[]; rows: ReportRow[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key}>{row[column.key] ?? "—"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReportsPage() {
  const [month, setMonth] = useState(thisMonth);
  const { data, isPending, error } = useQuery({
    queryKey: ["reports", month],
    queryFn: () => fetchReport(month),
    enabled: month !== "",
  });
  const download = useMutation({
    mutationFn: (table: ReportTable) => downloadReport(month, table),
  });

  return (
    <section className="stack">
      <h1>Reports</h1>
      <div className="card stack">
        <label className="text-field">
          Month
          <input
            type="month"
            value={month}
            max={thisMonth()}
            onChange={(e) => setMonth(e.target.value)}
          />
        </label>
        {download.isError && (
          <ErrorMessage
            error={download.error}
            fallback="Could not download the file."
          />
        )}
      </div>
      {month && isPending && <p className="page-loading">Loading…</p>}
      {error && (
        <ErrorMessage error={error} fallback="Could not load the report." />
      )}
      {data && (
        <>
          <div className="stats">
            {data.columns.days.slice(1).map((column) => (
              <div key={column.key} className="stat">
                <span className="stat__value">
                  {data.totals[column.key] ?? "—"}
                </span>
                <span className="stat__label">{column.label}</span>
              </div>
            ))}
          </div>
          {TABLES.map(([table, title]) => (
            <section key={table} className="card stack">
              <h2>
                {title}, {data.label}
              </h2>
              {data[table].length === 0 ? (
                <p className="muted">No cleaning requests in this month.</p>
              ) : (
                <Table columns={data.columns[table]} rows={data[table]} />
              )}
              <div className="choice-row">
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={download.isPending}
                  onClick={() => download.mutate(table)}
                >
                  Download CSV
                </button>
              </div>
            </section>
          ))}
        </>
      )}
    </section>
  );
}
