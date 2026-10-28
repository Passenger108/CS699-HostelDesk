import type { CleaningRequest, Offer } from "./cleaning";
import type { WorkerProfile } from "./profile";

export interface Worker extends WorkerProfile {
  id: number;
  name: string;
  tasks: { id: number; room: string; status: string }[];
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
