import type { AppNotification, NotificationList } from "../types/notification";
import { apiFetch } from "./client";

type ReadResponse = { notification: AppNotification; unread_count: number };

export const fetchNotifications = (unreadOnly = false) =>
  apiFetch<NotificationList>(
    unreadOnly ? "/notifications?unread=true" : "/notifications",
  );

export const fetchUnreadCount = () =>
  apiFetch<{ unread_count: number }>("/notifications/unread-count");

export const markNotificationRead = (id: number) =>
  apiFetch<ReadResponse>(`/notifications/${id}/read`, { method: "PATCH" });

export const markNotificationUnread = (id: number) =>
  apiFetch<ReadResponse>(`/notifications/${id}/unread`, { method: "PATCH" });
