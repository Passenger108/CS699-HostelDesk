import type { RequestStatus } from "../../types/cleaning";
import { statusTone } from "./labels";

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
