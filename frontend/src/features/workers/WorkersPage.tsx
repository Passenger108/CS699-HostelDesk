import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchWorkers } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import { LocationForm } from "./LocationForm";

export function WorkersPage() {
  const [editing, setEditing] = useState<number | null>(null);
  const { data, error } = useQuery({
    queryKey: ["workers"],
    queryFn: fetchWorkers,
    refetchInterval: 30_000,
  });

  if (error)
    return <ErrorMessage error={error} fallback="Could not load workers." />;
  if (!data) return <p className="page-loading">Loading…</p>;
  return (
    <section className="stack">
      <h1>Workers</h1>
      {data.workers.length === 0 && <p className="muted">No workers yet.</p>}
      {data.workers.map((worker) => (
        <article key={worker.id} className="card stack">
          <h2>{worker.name}</h2>
          <p className="muted">
            {worker.availability_label} ·{" "}
            {worker.last_location?.label ?? "No location"} ·{" "}
            {worker.location_note} ·{" "}
            {worker.tasks.map((t) => `${t.room}: ${t.status}`).join(", ") ||
              "No tasks"}
          </p>
          {editing === worker.id ? (
            <LocationForm
              workerId={worker.id}
              withReason
              onDone={() => setEditing(null)}
            />
          ) : (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setEditing(worker.id)}
            >
              Correct location
            </button>
          )}
        </article>
      ))}
    </section>
  );
}
