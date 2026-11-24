import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { requestStep, uploadProof } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { ChecklistItem, CleaningRequest } from "../../types/cleaning";
import { ProofImage } from "./ProofImage";
import { useTimeLeft } from "./TaskSteps";

const ITEMS: [ChecklistItem, string][] = [
  ["swept", "Floor swept"],
  ["mopped", "Floor mopped"],
  ["balcony_cleaned", "Balcony cleaned"],
  ["fan_cleaned", "Fan cleaned"],
];
const NONE_TICKED = Object.fromEntries(
  ITEMS.map(([item]) => [item, false]),
) as Record<ChecklistItem, boolean>;

function useRefresh() {
  const queryClient = useQueryClient();
  return () =>
    ["cleaning", "me", "workers", "notifications", "credits"].forEach((key) =>
      queryClient.invalidateQueries({ queryKey: [key] }),
    );
}

function WorkerFinish({ request }: { request: CleaningRequest }) {
  const refresh = useRefresh();
  const [ticked, setTicked] = useState(NONE_TICKED);
  const [photo, setPhoto] = useState<File | null>(null);
  const [picker, setPicker] = useState(0);
  const upload = useMutation({
    mutationFn: (file: File) => uploadProof(request.id, file),
    onSuccess: () => [setPhoto(null), setPicker(picker + 1)],
    onSettled: refresh,
  });
  const finish = useMutation({
    mutationFn: () =>
      requestStep(request.id, "complete", { checklist: ticked }),
    onSettled: refresh,
  });
  const allTicked = ITEMS.every(([item]) => ticked[item]);

  return (
    <div className="stack">
      <h3>Finish the room</h3>
      <fieldset className="choice-group">
        <legend>Checklist</legend>
        {ITEMS.map(([item, label]) => (
          <label key={item} className="choice">
            <input
              type="checkbox"
              checked={ticked[item]}
              onChange={(e) =>
                setTicked({ ...ticked, [item]: e.target.checked })
              }
            />
            {label}
          </label>
        ))}
      </fieldset>
      <label className="text-field">
        Photo of the cleaned room
        <input
          key={picker}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
        />
      </label>
      <p className="muted">
        Take or choose a photo: JPEG, PNG or WebP, up to 10 MB.
      </p>
      <div className="choice-row">
        <button
          type="button"
          className="btn btn--ghost"
          disabled={!photo || upload.isPending}
          onClick={() => photo && upload.mutate(photo)}
        >
          {upload.isPending
            ? "Uploading…"
            : request.completion
              ? "Replace photo"
              : "Upload photo"}
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={
            !allTicked ||
            !request.actions.includes("complete") ||
            finish.isPending
          }
          onClick={() => finish.mutate()}
        >
          {finish.isPending ? "Saving…" : "Mark the room clean"}
        </button>
      </div>
      {!request.completion && (
        <p className="muted">Upload a photo and tick every item to finish.</p>
      )}
      {upload.isError && (
        <ErrorMessage
          error={upload.error}
          fallback="Could not upload the photo."
        />
      )}
      {finish.isError && (
        <ErrorMessage
          error={finish.error}
          fallback="Could not finish. Try again."
        />
      )}
    </div>
  );
}

function StudentAnswer({ request }: { request: CleaningRequest }) {
  const refresh = useRefresh();
  const [disputing, setDisputing] = useState(false);
  const [reason, setReason] = useState("");
  const left = useTimeLeft(request.completion?.confirm_deadline ?? undefined);
  const answer = useMutation({
    mutationFn: (step: "confirm" | "dispute") =>
      requestStep(
        request.id,
        step,
        step === "dispute" ? { reason } : undefined,
      ),
    onSettled: refresh,
  });

  return (
    <div className="confirm" role="group" aria-label="Confirm the cleaning">
      <p>
        <strong>Is your room clean?</strong> {request.completion?.confirm_label}
        {left && ` (${left})`}. If you do nothing, it closes as cleaned.
      </p>
      {disputing && (
        <label className="text-field">
          What is wrong?
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={500}
            rows={2}
          />
        </label>
      )}
      <div className="choice-row">
        <button
          type="button"
          className="btn btn--primary"
          disabled={answer.isPending}
          onClick={() => answer.mutate("confirm")}
        >
          Yes, it is clean
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={answer.isPending || (disputing && !reason.trim())}
          onClick={() =>
            disputing ? answer.mutate("dispute") : setDisputing(true)
          }
        >
          {disputing ? "Send dispute" : "No, dispute it"}
        </button>
      </div>
      {answer.isError && (
        <ErrorMessage
          error={answer.error}
          fallback="Could not save. Try again."
        />
      )}
    </div>
  );
}

function DisputeDecision({ request }: { request: CleaningRequest }) {
  const refresh = useRefresh();
  const [outcome, setOutcome] = useState<"valid" | "unsatisfactory">("valid");
  const [goodwill, setGoodwill] = useState(false);
  const [reason, setReason] = useState("");
  const decide = useMutation({
    mutationFn: () =>
      requestStep(request.id, "resolve-dispute", {
        outcome,
        reason,
        lock_version: request.lock_version,
        goodwill: outcome === "unsatisfactory" && goodwill,
      }),
    onSettled: refresh,
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        decide.mutate();
      }}
    >
      <h3>Decide the dispute</h3>
      <fieldset className="choice-group">
        <legend>Was the cleaning done properly?</legend>
        <label className="choice">
          <input
            type="radio"
            checked={outcome === "valid"}
            onChange={() => setOutcome("valid")}
          />
          Yes, valid: the student's credit is used
        </label>
        <label className="choice">
          <input
            type="radio"
            checked={outcome === "unsatisfactory"}
            onChange={() => setOutcome("unsatisfactory")}
          />
          No, unsatisfactory: the credit goes back to the student
        </label>
        {outcome === "unsatisfactory" && (
          <label className="choice">
            <input
              type="checkbox"
              checked={goodwill}
              onChange={(e) => setGoodwill(e.target.checked)}
            />
            Also give one goodwill credit (expires next Monday)
          </label>
        )}
      </fieldset>
      <label className="text-field">
        Reason for your decision
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
          rows={2}
        />
      </label>
      <div className="choice-row">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={!reason.trim() || decide.isPending}
        >
          {decide.isPending ? "Saving…" : "Save decision"}
        </button>
      </div>
      {decide.isError && (
        <ErrorMessage
          error={decide.error}
          fallback="Could not save the decision."
        />
      )}
    </form>
  );
}

export function CompletionPanel({ request }: { request: CleaningRequest }) {
  const can = (action: string) => request.actions.includes(action);
  const completion = request.completion;
  const ticked = completion?.checklist
    ? ITEMS.filter(([item]) => completion.checklist?.[item]).map(
        ([, label]) => label,
      )
    : [];

  return (
    <div className="stack">
      {can("add_proof") && <WorkerFinish request={request} />}
      {(can("confirm") || can("dispute")) && (
        <StudentAnswer request={request} />
      )}
      {completion?.dispute_reason && (
        <p className="request-card__note">
          Dispute: “{completion.dispute_reason}”
        </p>
      )}
      {completion && !request.is_active && request.resolution_reason && (
        <p className="request-card__note">
          Decision: {request.resolution_reason}
        </p>
      )}
      {ticked.length > 0 && (
        <p className="muted">Checklist done: {ticked.join(", ")}.</p>
      )}
      {completion && <ProofImage completion={completion} />}
      {can("resolve_dispute") && <DisputeDecision request={request} />}
    </div>
  );
}
