import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchLocations, moveWorker } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";

export function LocationForm({
  workerId,
  withReason = false,
  onDone,
}: {
  workerId: number | "me";
  withReason?: boolean;
  onDone?: () => void;
}) {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["hostel", "locations"],
    queryFn: fetchLocations,
  });
  const [locationId, setLocationId] = useState("");
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () => moveWorker(workerId, Number(locationId), reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workers"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      onDone?.();
    },
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <label className="text-field">
        Floor and wing
        <select
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
          required
        >
          <option value="">Choose where</option>
          {data?.locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.label}
            </option>
          ))}
        </select>
      </label>
      {withReason && (
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
      )}
      {save.isError && (
        <ErrorMessage error={save.error} fallback="Could not save." />
      )}
      <button
        type="submit"
        className="btn btn--primary"
        disabled={save.isPending}
      >
        {save.isPending ? "Saving…" : "Update location"}
      </button>
    </form>
  );
}
