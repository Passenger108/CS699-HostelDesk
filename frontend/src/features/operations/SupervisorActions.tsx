import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { approveRequest, changeRequest } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest, Priority } from "../../types/cleaning";
import { PRIORITY_LABELS } from "../cleaning/labels";
import { AssignPanel } from "./AssignPanel";

export function SupervisorActions({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const onSettled = () =>
    queryClient.invalidateQueries({ queryKey: ["cleaning"] });
  const [priority, setPriority] = useState(request.priority);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const approve = useMutation({
    mutationFn: () => approveRequest(request.id),
    onSettled,
  });
  const change = useMutation({
    mutationFn: () =>
      changeRequest(request.id, {
        lock_version: request.lock_version,
        reason,
        ...(priority !== request.priority && { priority }),
        ...(from && {
          availability_mode: "TIME_WINDOW",
          window_start: from,
          window_end: to,
        }),
      }),
    onSuccess: () => [setReason(""), setFrom(""), setTo("")],
    onSettled,
  });

  return (
    <>
      {request.actions.includes("approve") && (
        <button
          type="button"
          className="btn btn--primary"
          disabled={approve.isPending}
          onClick={() => approve.mutate()}
        >
          {approve.isPending ? "Approving…" : "Approve"}
        </button>
      )}
      {approve.isError && (
        <ErrorMessage error={approve.error} fallback="Could not approve." />
      )}
      {request.actions.includes("offer") && <AssignPanel request={request} />}
      {request.actions.includes("change") && (
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            change.mutate();
          }}
        >
          <h3>Change priority or time</h3>
          <label className="text-field">
            Priority
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
            >
              {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="time-window">
            <label>
              New window from
              <input
                type="time"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                required={Boolean(to)}
              />
            </label>
            <label>
              To
              <input
                type="time"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                required={Boolean(from)}
              />
            </label>
          </div>
          <label className="text-field">
            Reason
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
              rows={2}
              required
            />
          </label>
          {change.isError && (
            <ErrorMessage error={change.error} fallback="Could not save." />
          )}
          <button
            type="submit"
            className="btn btn--ghost"
            disabled={change.isPending}
          >
            {change.isPending ? "Saving…" : "Save change"}
          </button>
        </form>
      )}
    </>
  );
}
