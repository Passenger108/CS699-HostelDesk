import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { takeBackRequest } from "../../api/cleaning";
import { fetchWorkers } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";

export function TakeBackForm({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [workerId, setWorkerId] = useState(0);
  const workers = useQuery({
    queryKey: ["workers"],
    queryFn: fetchWorkers,
  }).data?.workers.filter(
    (w) =>
      w.availability !== "OFF_DUTY" && w.id !== request.assigned_worker?.id,
  );
  const takeBack = useMutation({
    mutationFn: () =>
      takeBackRequest(request.id, {
        reason,
        lock_version: request.lock_version,
        ...(workerId && { worker_id: workerId }),
      }),
    onSettled: () =>
      ["cleaning", "workers"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        takeBack.mutate();
      }}
    >
      <h3>Take back from {request.assigned_worker?.name}</h3>
      <label className="text-field">
        Reason for taking it back
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          rows={2}
          required
        />
      </label>
      <label className="text-field">
        Offer it to
        <select
          value={workerId}
          onChange={(e) => setWorkerId(Number(e.target.value))}
        >
          <option value={0}>Nobody yet, choose later</option>
          {workers?.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name} · {w.availability_label}
            </option>
          ))}
        </select>
      </label>
      {takeBack.isError && (
        <ErrorMessage
          error={takeBack.error}
          fallback="Could not take it back."
        />
      )}
      <button
        type="submit"
        className="btn btn--ghost"
        disabled={takeBack.isPending}
      >
        {takeBack.isPending ? "Taking back…" : "Take back"}
      </button>
    </form>
  );
}
