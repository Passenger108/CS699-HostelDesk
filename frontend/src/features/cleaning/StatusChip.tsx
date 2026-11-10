import type { Delay, RequestStatus } from "../../types/cleaning";
import { DELAY_BADGES, statusTone } from "./labels";

export function StatusChip({
  request,
}: {
  request: { status: RequestStatus; status_label: string };
}) {
  return (
    <span className={`status-chip status-chip--${statusTone(request.status)}`}>
      {request.status_label}
    </span>
  );
}

export function DelayBadge({ delay }: { delay: Delay | null }) {
  if (!delay || delay.state === "NOT_DUE") return null;
  const [label, tone] = DELAY_BADGES[delay.state];
  return <span className={`status-chip status-chip--${tone}`}>{label}</span>;
}
