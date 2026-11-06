import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { requestStep } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest, RequestStep } from "../../types/cleaning";

type Body = Record<string, string | number>;
type Choice = [action: string, step: RequestStep, label: string, body?: Body];

const STEPS: Choice[] = [
  ["set_off", "en-route", "Set off"],
  ["arrive", "arrive", "I have arrived"],
  ["start", "start", "Start cleaning"],
];
const CHOICES: Choice[] = [
  ["accept_wait", "accept-wait", "Wait 5 more minutes"],
  ["refuse_wait", "refuse-wait", "I can't wait"],
  ["no_answer", "student-unavailable", "Nobody answered"],
  ["come_in", "arrival-response", "Come in", { answer: "COME_IN" }],
  ["wait", "arrival-response", "Wait 5 minutes", { answer: "WAIT" }],
];
const DECISIONS = [
  ["resume", "Let the work continue"],
  ["find_new_worker", "Find a new worker"],
];

function useTimeLeft(deadline?: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!deadline) return null;
  const seconds = Math.max(0, Math.round((Date.parse(deadline) - now) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} left`;
}

export function TaskSteps({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const left = useTimeLeft(request.door?.deadline);
  const step = useMutation({
    mutationFn: ({ path, body }: { path: RequestStep; body?: Body }) =>
      requestStep(request.id, path, body),
    onSuccess: () => setReason(""),
    onSettled: () =>
      ["cleaning", "me", "workers", "notifications"].forEach((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
  });
  const can = (action: string) => request.actions.includes(action);
  const worker = can("report_problem");
  const deciding = can("resume") || can("find_new_worker");
  const button = ([action, path, label, body]: Choice, main = false) => (
    <button
      key={action}
      type="button"
      className={main ? "btn btn--primary" : "btn btn--ghost"}
      disabled={step.isPending || !can(action)}
      onClick={() => step.mutate({ path, body })}
    >
      {label}
    </button>
  );
  const reasonBox = (label: string) => (
    <label className="text-field">
      {label}
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={500}
        rows={2}
      />
    </label>
  );

  return (
    <div className="stack">
      {request.door && (
        <p className="request-card__note" role="status">
          {request.door.label}. {request.door.deadline_label}
          {left && ` (${left})`}.
        </p>
      )}
      {request.pause && (
        <p className="request-card__note">
          Paused while “{request.pause.from_label}”: {request.pause.reason}
        </p>
      )}
      {worker && (
        <div className="choice-row">
          {STEPS.map((choice) => button(choice, can(choice[0])))}
        </div>
      )}
      <div className="choice-row">
        {CHOICES.filter(([action]) => can(action)).map((choice) =>
          button(choice, choice[2] === "Come in"),
        )}
      </div>
      {(worker || deciding) && (
        <form className="stack" onSubmit={(e) => e.preventDefault()}>
          {reasonBox(worker ? "Problem" : "Reason for your decision")}
          <div className="choice-row">
            {worker &&
              button([
                "report_problem",
                "problem",
                "Report a problem",
                { reason },
              ])}
            {DECISIONS.filter(([action]) => can(action)).map(
              ([action, label]) =>
                button([
                  action,
                  "resolve-intervention",
                  label,
                  {
                    decision: action === "resume" ? "resume" : "reassign",
                    reason,
                    lock_version: request.lock_version,
                  },
                ]),
            )}
          </div>
        </form>
      )}
      {step.isError && (
        <ErrorMessage
          error={step.error}
          fallback="Could not save. Try again."
        />
      )}
    </div>
  );
}
