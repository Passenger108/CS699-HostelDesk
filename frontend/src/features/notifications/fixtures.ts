import type { AppNotification } from "../../types/notification";

export const supervisorMe = {
  user: {
    id: 3,
    role: "SUPERVISOR",
    login_id: "demo.supervisor",
    name: "Demo Supervisor",
    phone: "+91 90000 00003",
    email: null,
    locale: "en",
    account_status: "ACTIVE",
  },
  profile: null,
};

export const newRequestNotice: AppNotification = {
  id: 11,
  type: "NEW_REQUEST",
  title: "New cleaning request",
  body: "Room A105 asked for cleaning.",
  request_id: 7,
  is_read: false,
  read_at: null,
  created_at: "2026-10-20T04:30:00+00:00",
};

export const oldNotice: AppNotification = {
  id: 10,
  type: "REQUEST_CANCELLED_BY_STUDENT",
  title: "Request cancelled",
  body: "The student in room A102 cancelled their cleaning request.",
  request_id: 6,
  is_read: true,
  read_at: "2026-10-19T05:00:00+00:00",
  created_at: "2026-10-19T04:00:00+00:00",
};
