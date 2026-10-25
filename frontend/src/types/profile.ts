import type { LocationInfo, RoomInfo } from "./hostel";

export interface StudentProfile {
  roll_number: string;
  room: RoomInfo | null;
  guardian_contact?: string | null;
}

export interface WorkerProfile {
  employee_id: string;
  shift: string | null;
  availability: "AVAILABLE" | "BUSY" | "OFF_DUTY";
  availability_label: string;
  last_location: LocationInfo | null;
  location_updated_at: string | null;
  location_age_minutes: number | null;
  freshness: "FRESH" | "STALE" | "UNKNOWN";
  location_note: string;
}

export type Profile = StudentProfile | WorkerProfile | null;
