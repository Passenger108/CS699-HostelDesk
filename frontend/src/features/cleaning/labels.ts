import type { Priority, RequestStatus } from "../../types/cleaning";

export const PRIORITY_LABELS: Record<Priority, string> = {
  NORMAL: "Normal",
  URGENT: "Urgent",
  EMERGENCY: "Emergency",
};

export type StatusTone =
  | "waiting"
  | "working"
  | "attention"
  | "done"
  | "stopped";

const TONES: Partial<Record<RequestStatus, StatusTone>> = {
  ACCEPTED_QUEUED: "working",
  EN_ROUTE: "working",
  ARRIVED: "working",
  CLEANING_IN_PROGRESS: "working",
  AWAITING_STUDENT_RESCHEDULE: "attention",
  AWAITING_STUDENT_CONFIRMATION: "attention",
  SUPERVISOR_INTERVENTION: "attention",
  DISPUTED: "attention",
  CLOSED_SUCCESSFUL: "done",
  CLOSED_VALID_AFTER_REVIEW: "done",
  CLOSED_UNSATISFACTORY: "stopped",
  STUDENT_UNAVAILABLE: "stopped",
  CANCELLED_BY_STUDENT: "stopped",
  CANCELLED_BY_SUPERVISOR: "stopped",
  EXPIRED: "stopped",
};

export function statusTone(status: RequestStatus): StatusTone {
  return TONES[status] ?? "waiting";
}
