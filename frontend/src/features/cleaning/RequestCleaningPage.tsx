import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchActiveRequest, submitCleaningRequest } from "../../api/cleaning";
import { ApiError } from "../../api/client";
import { fetchMyCredits } from "../../api/credits";
import { fetchMyProfile } from "../../api/profile";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { NewCleaningRequest } from "../../types/cleaning";
import type { StudentProfile } from "../../types/profile";
import { AvailabilityFields, NOW } from "./AvailabilityFields";

const NOTE_LIMIT = 500;

function newClientKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto)
    return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function creditMessage(urgent: boolean, available: number): string {
  if (available > 0) {
    return `This reserves 1 of your ${available} available credit${available === 1 ? "" : "s"}. You get it back if the request is cancelled.`;
  }
  if (urgent)
    return "You have no credit, so none will be used. The request will be awaiting supervisor approval.";
  return "You have no credit available. You can still send an urgent request with a reason.";
}

export function RequestCleaningPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [clientKey] = useState(newClientKey);
  const [when, setWhen] = useState(NOW);
  const [urgent, setUrgent] = useState(false);
  const [urgentReason, setUrgentReason] = useState("");
  const [note, setNote] = useState("");

  const profile = useQuery({
    queryKey: ["me", "profile"],
    queryFn: fetchMyProfile,
  });
  const credits = useQuery({ queryKey: ["credits"], queryFn: fetchMyCredits });
  const active = useQuery({
    queryKey: ["cleaning", "active"],
    queryFn: fetchActiveRequest,
  });

  const submit = useMutation({
    mutationFn: (body: NewCleaningRequest) => submitCleaningRequest(body),
    onSuccess: (res) => {
      queryClient.setQueryData(["cleaning", "active"], {
        request: res.request,
      });
      queryClient.invalidateQueries({ queryKey: ["cleaning"] });
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      navigate("/", { replace: true });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        queryClient.invalidateQueries({ queryKey: ["cleaning", "active"] });
        queryClient.invalidateQueries({ queryKey: ["credits"] });
      }
    },
  });

  if (profile.isPending || credits.isPending || active.isPending) {
    return <p className="page-loading">Loading…</p>;
  }
  const loadError = profile.error ?? credits.error ?? active.error;
  if (loadError)
    return (
      <ErrorMessage error={loadError} fallback="Could not load the form." />
    );

  if (active.data?.request) {
    return (
      <section className="card">
        <h1>Request cleaning</h1>
        <p>You already have an active cleaning request.</p>
        <Link to="/" className="btn btn--primary">
          See it on Home
        </Link>
      </section>
    );
  }

  const room = (profile.data?.profile as StudentProfile | null)?.room ?? null;
  const available = credits.data?.balance.available ?? 0;
  const phone = profile.data?.user.phone?.trim() ?? "";
  const blocked = !urgent && available === 0;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const body: NewCleaningRequest = {
      ...when,
      priority: urgent ? "URGENT" : "NORMAL",
      client_key: clientKey,
    };
    if (urgent) body.urgent_reason = urgentReason;
    if (note.trim()) body.note = note;
    submit.mutate(body);
  }

  return (
    <form className="stack" onSubmit={onSubmit}>
      <h1>Request cleaning</h1>

      <section className="card">
        <h2>Your room</h2>
        {room ? (
          <p>
            <strong>{room.number}</strong> · {room.floor_label}, Wing{" "}
            {room.wing}
          </p>
        ) : (
          <p className="error" role="alert">
            No room is assigned to you yet. Contact the hostel office.
          </p>
        )}
        <p className="muted">
          The room comes from your profile and cannot be changed here.
        </p>
        {!phone && (
          <p className="error" role="alert">
            Your profile has no phone number. Please contact the hostel office.
          </p>
        )}
      </section>

      <AvailabilityFields
        when={when}
        onChange={setWhen}
        legend="When are you available?"
      />

      <fieldset className="card choice-group">
        <legend>How soon?</legend>
        <label className="choice">
          <input
            type="radio"
            name="priority"
            checked={!urgent}
            onChange={() => setUrgent(false)}
          />
          Normal
        </label>
        <label className="choice">
          <input
            type="radio"
            name="priority"
            checked={urgent}
            onChange={() => setUrgent(true)}
          />
          Urgent
        </label>
        {urgent && (
          <label className="text-field">
            Why is it urgent?
            <textarea
              value={urgentReason}
              onChange={(e) => setUrgentReason(e.target.value)}
              maxLength={NOTE_LIMIT}
              rows={2}
              required
            />
          </label>
        )}
      </fieldset>

      <section className="card">
        <label className="text-field">
          Note for the worker (optional)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={NOTE_LIMIT}
            rows={3}
          />
        </label>
        <p className="muted text-field__count">
          {note.length}/{NOTE_LIMIT}
        </p>
      </section>

      <section className="card">
        <h2>Credit</h2>
        <p className={blocked ? "error" : undefined}>
          {creditMessage(urgent, available)}
        </p>
      </section>

      {submit.isError && (
        <ErrorMessage
          error={submit.error}
          fallback="Could not send the request."
        />
      )}
      <button
        type="submit"
        className="btn btn--primary"
        disabled={blocked || !room || !phone || submit.isPending}
      >
        {submit.isPending ? "Sending…" : "Send request"}
      </button>
    </form>
  );
}
