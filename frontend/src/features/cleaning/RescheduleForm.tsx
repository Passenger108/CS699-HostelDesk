import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { requestStep } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";
import { AvailabilityFields, NOW } from "./AvailabilityFields";

export function RescheduleForm({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [when, setWhen] = useState(NOW);
  const save = useMutation({
    mutationFn: () => requestStep(request.id, "reschedule", when),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cleaning"] }),
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <p className="request-card__note" role="status">
        Your time ended before a worker could come.{" "}
        {request.reschedule?.deadline_label}, or the request expires and your
        credit comes back.
      </p>
      <AvailabilityFields
        when={when}
        onChange={setWhen}
        legend="When are you free now?"
      />
      {save.isError && (
        <ErrorMessage
          error={save.error}
          fallback="Could not save. Try again."
        />
      )}
      <div className="choice-row">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={save.isPending}
        >
          {save.isPending ? "Saving…" : "Save new time"}
        </button>
      </div>
    </form>
  );
}
