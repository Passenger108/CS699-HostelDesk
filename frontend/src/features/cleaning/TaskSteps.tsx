import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { requestStep } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest, RequestStep } from "../../types/cleaning";
import { ETAS } from "../workers/OfferCard";

type Body = Record<string, string | number>;
type Choice = [
  action: string,
  step: RequestStep,
  label: string,
  body?: Body,
  method?: string,
];

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
  ["flag_delay", "flag-delay", "Tell the supervisor the worker is late"],
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
  const [eta, setEta] = useState(ETAS[1]);
  const left = useTimeLeft(request.door?.deadline);
  const etaLeft = useTimeLeft(request.delay?.expected_at);
  const step = useMutation({
    mutationFn: ([, path, , body, method]: Choice) =>
      requestStep(request.id, path, body, method),
    onSuccess: () => setReason(""),
    onSettled: () =>
      ["cleaning", "me", "workers", "notifications"].forEach((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
  });
  const can = (action: string) => request.actions.includes(action);
  const worker = can("report_problem");
  const decide = { reason, lock_version: request.lock_version };
  const decisions = (
    [
      [
        "resume",
        "resolve-intervention",
        "Let the work continue",
        { ...decide, decision: "resume" },
      ],
      [
        "find_new_worker",
        "resolve-intervention",
        "Find a new worker",
        { ...decide, decision: "reassign" },
      ],
      ["resolve_delay", "resolve-delay", "Mark the delay as handled", decide],
    ] as Choice[]
  ).filter(([action]) => can(action));
  const button = (choice: Choice, main = false) => (
    <button
      key={choice[0]}
      type="button"
      className={main ? "btn btn--primary" : "btn btn--ghost"}
      disabled={step.isPending || !can(choice[0])}
      onClick={() => step.mutate(choice)}
    >
      {choice[2]}
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
      {request.delay && (
        <p className="request-card__note" role="status">
          {request.delay.label}
          {request.delay.state === "NOT_DUE" && etaLeft && ` (${etaLeft})`}.
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
      {can("update_eta") && (
        <div className="choice-row">
          <label className="text-field">
            New arrival time
            <select
              value={eta}
              onChange={(e) => setEta(Number(e.target.value))}
            >
              {ETAS.map((minutes) => (
                <option key={minutes} value={minutes}>
                  In {minutes} minutes
                </option>
              ))}
            </select>
          </label>
          {button([
            "update_eta",
            "eta",
            "Update arrival time",
            { eta_minutes: eta },
            "PATCH",
          ])}
        </div>
      )}
      {(worker || decisions.length > 0) && (
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
            {decisions.map((choice, index) => button(choice, index === 0))}
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
