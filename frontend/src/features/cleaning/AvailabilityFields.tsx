import type { AvailabilityMode } from "../../types/cleaning";

export type When = {
  availability_mode: AvailabilityMode;
  window_start: string;
  window_end: string;
};

export const NOW: When = {
  availability_mode: "AVAILABLE_NOW",
  window_start: "",
  window_end: "",
};

const OPTIONS: [AvailabilityMode, string][] = [
  ["AVAILABLE_NOW", "I am available now"],
  ["TIME_WINDOW", "A time window today"],
  ["ANY_TIME_TODAY", "Any time today"],
];

export function AvailabilityFields({
  when,
  onChange,
  legend,
}: {
  when: When;
  onChange: (when: When) => void;
  legend: string;
}) {
  const set = (change: Partial<When>) => onChange({ ...when, ...change });
  const time = (key: "window_start" | "window_end", label: string) => (
    <label>
      {label}
      <input
        type="time"
        value={when[key]}
        onChange={(e) => set({ [key]: e.target.value })}
        required
      />
    </label>
  );
  return (
    <fieldset className="card choice-group">
      <legend>{legend}</legend>
      {OPTIONS.map(([value, label]) => (
        <label key={value} className="choice">
          <input
            type="radio"
            name="availability"
            value={value}
            checked={when.availability_mode === value}
            onChange={() => set({ availability_mode: value })}
          />
          {label}
        </label>
      ))}
      {when.availability_mode === "TIME_WINDOW" && (
        <div className="time-window">
          {time("window_start", "From")}
          {time("window_end", "To")}
        </div>
      )}
    </fieldset>
  );
}
