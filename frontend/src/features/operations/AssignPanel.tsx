import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchRecommendations,
  fetchWorkers,
  sendOffer,
} from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";

export function AssignPanel({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [workerId, setWorkerId] = useState(0);
  const picks = useQuery({
    queryKey: ["cleaning", "recommendations", request.id],
    queryFn: () => fetchRecommendations(request.id),
  }).data?.recommendations;
  const workers = useQuery({ queryKey: ["workers"], queryFn: fetchWorkers })
    .data?.workers;
  const others = (workers ?? [])
    .filter((w) => w.availability !== "OFF_DUTY")
    .filter((w) => !picks?.some((pick) => pick.worker.id === w.id))
    .map((worker) => ({ worker, reason: "Not recommended.", warnings: [] }));
  const offer = useMutation({
    mutationFn: () => sendOffer(request.id, workerId, request.lock_version),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cleaning"] }),
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        offer.mutate();
      }}
    >
      <h3>Offer to a worker</h3>
      {[...(picks ?? []), ...others].map(({ worker, reason, warnings }) => (
        <label key={worker.id} className="choice">
          <input
            type="radio"
            name="worker"
            checked={workerId === worker.id}
            onChange={() => setWorkerId(worker.id)}
          />
          <span>
            <strong>{worker.name}</strong> · {reason}{" "}
            <span className="error">{warnings.join(" ")}</span>
          </span>
        </label>
      ))}
      {offer.isError && (
        <ErrorMessage
          error={offer.error}
          fallback="Could not send the offer."
        />
      )}
      <button
        type="submit"
        className="btn btn--primary"
        disabled={!workerId || offer.isPending}
      >
        {offer.isPending ? "Sending…" : "Send offer"}
      </button>
    </form>
  );
}
