import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { cancelCleaningRequest, fetchActiveRequest } from "../../api/cleaning";
import { ApiError } from "../../api/client";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";
import { SupervisorActions } from "../operations/SupervisorActions";
import { PRIORITY_LABELS } from "./labels";
import { RequestTimeline } from "./RequestTimeline";
import { StatusChip } from "./StatusChip";

function CancelControl({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const cancel = useMutation({
    mutationFn: () => cancelCleaningRequest(request.id),
    onSuccess: () => {
      setConfirming(false);
      queryClient.invalidateQueries({ queryKey: ["cleaning"] });
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        queryClient.invalidateQueries({ queryKey: ["cleaning"] });
      }
    },
  });

  if (!confirming) {
    return (
      <button
        type="button"
        className="btn btn--ghost"
        onClick={() => setConfirming(true)}
      >
        Cancel request
      </button>
    );
  }
  return (
    <div className="confirm" role="group" aria-label="Confirm cancel">
      <p>
        Cancel this request?
        {request.credit_reservation === "RESERVED" &&
          " Your credit will be returned."}
      </p>
      <div className="confirm__buttons">
        <button
          type="button"
          className="btn btn--danger"
          disabled={cancel.isPending}
          onClick={() => cancel.mutate()}
        >
          {cancel.isPending ? "Cancelling…" : "Yes, cancel"}
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={cancel.isPending}
          onClick={() => setConfirming(false)}
        >
          Keep request
        </button>
      </div>
      {cancel.isError && (
        <ErrorMessage
          error={cancel.error}
          fallback="Could not cancel. Try again."
        />
      )}
    </div>
  );
}

export function RequestDetails({ request }: { request: CleaningRequest }) {
  return (
    <>
      <div className="request-card__head">
        <StatusChip request={request} />
        {request.priority !== "NORMAL" && (
          <span className="chip">{PRIORITY_LABELS[request.priority]}</span>
        )}
      </div>
      <dl className="field-grid">
        <div className="field">
          <dt>Room</dt>
          <dd>
            {request.room.number} · {request.room.floor_label}, Wing{" "}
            {request.room.wing}
          </dd>
        </div>
        <div className="field">
          <dt>When</dt>
          <dd>{request.availability.label}</dd>
        </div>
        <div className="field">
          <dt>Credit</dt>
          <dd>
            {request.credit_reservation === "RESERVED"
              ? "1 reserved"
              : "None used"}
          </dd>
        </div>
      </dl>
      {request.urgent_reason && (
        <p className="request-card__note">Urgent: {request.urgent_reason}</p>
      )}
      {request.note && <p className="request-card__note">“{request.note}”</p>}
      <h3>Timeline</h3>
      <RequestTimeline events={request.timeline} />
      {request.actions.includes("cancel") && (
        <CancelControl request={request} />
      )}
      <SupervisorActions
        key={`${request.id}-${request.lock_version}`}
        request={request}
      />
    </>
  );
}

export function ActiveRequestCard() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["cleaning", "active"],
    queryFn: fetchActiveRequest,
    refetchInterval: 15_000,
  });

  return (
    <section className="card request-card">
      <h2>Room cleaning</h2>
      {isPending && <p className="muted">Loading…</p>}
      {isError && (
        <ErrorMessage error={error} fallback="Could not load your request." />
      )}
      {data && data.request && <RequestDetails request={data.request} />}
      {data && !data.request && (
        <>
          <p className="muted">You have no active cleaning request.</p>
          <Link to="/request" className="btn btn--primary btn--link">
            Request cleaning
          </Link>
        </>
      )}
    </section>
  );
}
