import type { Role } from './user';

export type RequestStatus =
  | 'SUBMITTED'
  | 'AWAITING_ASSIGNMENT'
  | 'OFFERED'
  | 'AWAITING_REASSIGNMENT'
  | 'ACCEPTED_QUEUED'
  | 'AWAITING_STUDENT_RESCHEDULE'
  | 'EN_ROUTE'
  | 'ARRIVED'
  | 'CLEANING_IN_PROGRESS'
  | 'AWAITING_STUDENT_CONFIRMATION'
  | 'SUPERVISOR_INTERVENTION'
  | 'DISPUTED'
  | 'CLOSED_SUCCESSFUL'
  | 'CLOSED_VALID_AFTER_REVIEW'
  | 'CLOSED_UNSATISFACTORY'
  | 'STUDENT_UNAVAILABLE'
  | 'CANCELLED_BY_STUDENT'
  | 'CANCELLED_BY_SUPERVISOR'
  | 'EXPIRED';

export type Priority = 'NORMAL' | 'URGENT' | 'EMERGENCY';
export type AvailabilityMode = 'AVAILABLE_NOW' | 'TIME_WINDOW' | 'ANY_TIME_TODAY';

export interface Person {
  id: number;
  name: string;
  role: Role;
}

export interface RequestEvent {
  id: number;
  event_type: string;
  label: string;
  old_state: RequestStatus | null;
  new_state: RequestStatus;
  actor: Person | null;
  occurred_at: string;
}

export interface CleaningRequest {
  id: number;
  status: RequestStatus;
  status_label: string;
  is_active: boolean;
  priority: Priority;
  urgent_reason: string | null;
  note: string | null;
  availability: {
    mode: AvailabilityMode;
    window_start: string | null;
    window_end: string | null;
    available_until: string;
  };
  room: { number: string; floor: number; floor_label: string; wing: string };
  contact_phone: string;
  credit_reservation: 'NONE' | 'RESERVED' | 'CONSUMED' | 'RELEASED';
  student: Person;
  assigned_worker: Person | null;
  created_at: string;
  closed_at: string | null;
  resolution_reason: string | null;
  lock_version: number;
  actions: string[];
  timeline: RequestEvent[];
}

export interface NewCleaningRequest {
  availability_mode: AvailabilityMode;
  window_start?: string;
  window_end?: string;
  priority: 'NORMAL' | 'URGENT';
  urgent_reason?: string;
  note?: string;
  client_key: string;
}
