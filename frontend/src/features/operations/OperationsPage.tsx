import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchBoard, fetchRequest } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { RequestSummary } from "../../types/cleaning";
import { RequestDetails } from "../cleaning/ActiveRequestCard";
import { PRIORITY_LABELS } from "../cleaning/labels";
import { StatusChip } from "../cleaning/StatusChip";

function elapsed(now: string, since: string): string {
  const minutes = Math.max(
    0,
    Math.floor((Date.parse(now) - Date.parse(since)) / 60000),
  );
  return minutes < 60
    ? `${minutes} min`
    : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

function BoardCard({
  row,
  now,
  onOpen,
}: {
  row: RequestSummary;
  now: string;
  onOpen: () => void;
}) {
  return (
    <button type="button" className="card board__card" onClick={onOpen}>
      <span className="request-card__head">
        <StatusChip request={row} />
        {row.priority !== "NORMAL" && (
          <span className="chip">{PRIORITY_LABELS[row.priority]}</span>
        )}
      </span>
      <strong>Room {row.room.number}</strong>
      <span className="muted">
        {row.room.floor_label}, Wing {row.room.wing} · {row.availability.label}
      </span>
      <span className="muted">
        {row.assigned_worker?.name ?? "No worker"}
        {row.latest_eta_minutes !== null &&
          ` · ETA ${row.latest_eta_minutes} min`}{" "}
        · sent {elapsed(now, row.created_at)} ago
      </span>
    </button>
  );
}

function RequestDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, error } = useQuery({
    queryKey: ["cleaning", "request", id],
    queryFn: () => fetchRequest(id),
  });
  return (
    <aside className="drawer card request-card" aria-label="Request details">
      <button type="button" className="btn btn--ghost" onClick={onClose}>
        Close
      </button>
      {error && <ErrorMessage error={error} fallback="Could not load it." />}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && (
        <>
          <h2>
            Request {data.request.id} · {data.request.student.name}
          </h2>
          {data.request.offer?.status === "PENDING" && (
            <p className="request-card__note">{data.request.offer.summary}</p>
          )}
          <RequestDetails request={data.request} />
        </>
      )}
    </aside>
  );
}

export function OperationsPage() {
  const [openId, setOpenId] = useState<number | null>(null);
  const { data, error } = useQuery({
    queryKey: ["cleaning", "board"],
    queryFn: fetchBoard,
    refetchInterval: 10_000,
  });

  if (error)
    return <ErrorMessage error={error} fallback="Could not load the board." />;
  if (!data) return <p className="page-loading">Loading…</p>;
  return (
    <section className="stack">
      <h1>Operations</h1>
      <div className="board">
        {data.groups.map((group) => (
          <section
            key={group.key}
            className="board__column"
            aria-label={group.label}
          >
            <h2>
              {group.label} ({group.requests.length})
            </h2>
            {group.requests.length === 0 && <p className="muted">None</p>}
            {group.requests.map((row) => (
              <BoardCard
                key={row.id}
                row={row}
                now={data.generated_at}
                onOpen={() => setOpenId(row.id)}
              />
            ))}
          </section>
        ))}
      </div>
      {openId !== null && (
        <RequestDrawer id={openId} onClose={() => setOpenId(null)} />
      )}
    </section>
  );
}
