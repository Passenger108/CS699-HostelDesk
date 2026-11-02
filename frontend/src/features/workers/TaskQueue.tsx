import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { changeDuty, reorderQueue } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { Worker } from "../../types/worker";

export function TaskQueue({
  worker,
  self,
}: {
  worker: Worker;
  self?: boolean;
}) {
  const queryClient = useQueryClient();
  const onSettled = () =>
    ["workers", "me", "cleaning"].map((key) =>
      queryClient.invalidateQueries({ queryKey: [key] }),
    );
  const order = worker.tasks.filter((t) => t.movable).map((t) => t.id);
  const move = useMutation({
    mutationFn: ({ from, to }: { from: number; to: number }) => {
      const next = [...order];
      [next[from], next[to]] = [next[to], next[from]];
      return reorderQueue(self ? "me" : worker.id, next);
    },
    onSettled,
  });
  const duty = useMutation({
    mutationFn: changeDuty,
    onSettled,
  });
  const offDuty = worker.availability === "OFF_DUTY";
  const dutyPath = self
    ? offDuty
      ? "me/on-duty"
      : !worker.off_duty_requested_at && "me/off-duty-request"
    : worker.off_duty_requested_at &&
      (`${worker.id}/off-duty/approve` as const);
  const dutyLabel = self
    ? offDuty
      ? "Back on duty"
      : "Ask to go off duty"
    : "Approve off duty";

  return (
    <div className="stack">
      {worker.queue_warning && <p className="error">{worker.queue_warning}</p>}
      {worker.tasks.length === 0 && <p className="muted">No accepted tasks.</p>}
      <ol className="queue">
        {worker.tasks.map((task) => {
          const at = order.indexOf(task.id);
          return (
            <li key={task.id}>
              <span>
                <Link to={`/requests/${task.id}`}>Room {task.room}</Link> ·{" "}
                {task.status} · {task.due_label}
                {task.warning && <span className="error"> {task.warning}</span>}
              </span>
              {task.movable && (
                <span className="choice-row">
                  {(["up", "down"] as const).map((way) => {
                    const to = way === "up" ? at - 1 : at + 1;
                    return (
                      <button
                        key={way}
                        type="button"
                        className="btn btn--ghost"
                        aria-label={`Move room ${task.room} ${way}`}
                        disabled={
                          to < 0 || to >= order.length || move.isPending
                        }
                        onClick={() => move.mutate({ from: at, to })}
                      >
                        {way === "up" ? "Up" : "Down"}
                      </button>
                    );
                  })}
                </span>
              )}
            </li>
          );
        })}
      </ol>
      {self && worker.off_duty_requested_at && (
        <p className="muted">Waiting for the supervisor to approve off duty.</p>
      )}
      {!self && worker.off_duty_requested_at && (
        <p className="muted">Asked to go off duty.</p>
      )}
      {dutyPath && (
        <button
          type="button"
          className="btn btn--ghost"
          disabled={duty.isPending}
          onClick={() => duty.mutate(dutyPath)}
        >
          {dutyLabel}
        </button>
      )}
      {[move, duty].map(
        (m, i) =>
          m.isError && (
            <ErrorMessage key={i} error={m.error} fallback="Could not save." />
          ),
      )}
    </div>
  );
}
