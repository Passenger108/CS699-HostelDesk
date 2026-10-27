import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { answerOffer } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { WorkerOffer } from "../../types/worker";
import { RequestDetails } from "../cleaning/ActiveRequestCard";

const ETAS = Array.from({ length: 24 }, (_, i) => (i + 1) * 5);

function useSecondsLeft(deadline: string) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return Math.max(0, Math.floor((Date.parse(deadline) - now) / 1000));
}

export function OfferCard({ offer }: { offer: WorkerOffer }) {
  const queryClient = useQueryClient();
  const [eta, setEta] = useState(15);
  const [reason, setReason] = useState("");
  const left = useSecondsLeft(offer.response_deadline);
  const answer = useMutation({
    mutationFn: (accept: boolean) =>
      accept
        ? answerOffer(offer.id, "accept", { eta_minutes: eta })
        : answerOffer(offer.id, "decline", { reason }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["worker"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
  const closed = left === 0 || answer.isPending;
  const { request } = offer;

  return (
    <article className="card stack">
      <h2>New offer · Room {request.room.number}</h2>
      <p className={left ? "muted" : "error"}>
        {left
          ? `Answer within ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`
          : "Time is up"}
      </p>
      <RequestDetails request={request} />
      <p>
        {request.student.name} ·{" "}
        <a href={`tel:${request.contact_phone}`}>{request.contact_phone}</a>
      </p>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          answer.mutate(true);
        }}
      >
        <label className="text-field">
          I can be there in
          <select value={eta} onChange={(e) => setEta(Number(e.target.value))}>
            {ETAS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} minutes
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn btn--primary" disabled={closed}>
          Accept
        </button>
        <label className="text-field">
          Reason, if you decline
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={500}
            rows={2}
          />
        </label>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={closed}
          onClick={() => answer.mutate(false)}
        >
          Decline
        </button>
      </form>
      {answer.isError && (
        <ErrorMessage
          error={answer.error}
          fallback="Could not send your answer."
        />
      )}
    </article>
  );
}
