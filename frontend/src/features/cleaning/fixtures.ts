import type { CleaningRequest } from "../../types/cleaning";

export const studentMe = {
  user: {
    id: 1,
    role: "STUDENT",
    login_id: "demo.student",
    name: "Demo Student",
    phone: "+91 90000 00001",
    email: null,
    locale: "en",
    account_status: "ACTIVE",
  },
  profile: {
    roll_number: "DEMO24B001",
    room: {
      id: 5,
      number: "A105",
      floor: 1,
      floor_label: "Floor 1",
      wing: "A",
    },
  },
};

export function creditsWith(available: number) {
  return {
    balance: {
      available,
      standard_available: available,
      goodwill_available: 0,
      reserved: 0,
      consumed: 0,
      cap: 3,
      next_grant_at: "2026-10-25T18:30:00+00:00",
    },
    history: [],
  };
}

export const submittedRequest: CleaningRequest = {
  id: 7,
  status: "SUBMITTED",
  status_label: "Waiting for supervisor approval",
  is_active: true,
  priority: "NORMAL",
  urgent_reason: null,
  note: "Please clean the balcony",
  availability: {
    mode: "TIME_WINDOW",
    label: "Today, 2:00 pm to 3:30 pm",
    window_start: "2026-10-17T08:30:00+00:00",
    window_end: "2026-10-17T10:00:00+00:00",
    available_until: "2026-10-17T10:00:00+00:00",
  },
  room: { id: 5, number: "A105", floor: 1, floor_label: "Floor 1", wing: "A" },
  contact_phone: "+91 90000 00001",
  credit_reservation: "RESERVED",
  student: { id: 1, name: "Demo Student", role: "STUDENT" },
  assigned_worker: null,
  accepted_at: null,
  latest_eta_minutes: null,
  created_at: "2026-10-17T05:00:00+00:00",
  closed_at: null,
  resolution_reason: null,
  lock_version: 1,
  actions: ["cancel"],
  timeline: [
    {
      id: 1,
      event_type: "SUBMITTED",
      label: "Request submitted",
      old_state: null,
      new_state: "SUBMITTED",
      actor: { id: 1, name: "Demo Student", role: "STUDENT" },
      occurred_at: "2026-10-17T05:00:00+00:00",
    },
  ],
};
