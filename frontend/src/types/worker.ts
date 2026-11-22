import type { CleaningRequest, Offer } from "./cleaning";
import type { WorkerProfile } from "./profile";

export interface Worker extends WorkerProfile {
  id: number;
  name: string;
  tasks: QueueTask[];
  queue_warning: string | null;
  off_duty_requested_at: string | null;
  rating: RatingSummary;
}

export interface RatingSummary {
  count: number;
  average: number | null;
}

export interface MyFeedback extends RatingSummary {
  comments: string[];
}

export interface QueueTask {
  id: number;
  room: string;
  status: string;
  movable: boolean;
  due_label: string | null;
  warning: string | null;
}

export interface Recommendation {
  worker: Worker;
  reason: string;
  warnings: string[];
}

export interface WorkerOffer extends Offer {
  id: number;
  response_deadline: string;
  request: CleaningRequest;
}
