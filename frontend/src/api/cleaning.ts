import type {
  Board,
  CleaningRequest,
  NewCleaningRequest,
  RequestFilters,
  RequestChange,
  RequestPage,
  RequestStep,
} from "../types/cleaning";
import { apiFetch } from "./client";

type RequestResponse = { request: CleaningRequest };
type ActiveResponse = { request: CleaningRequest | null };

export const fetchActiveRequest = () =>
  apiFetch<ActiveResponse>("/cleaning/requests/active");

export const submitCleaningRequest = (body: NewCleaningRequest) =>
  apiFetch<RequestResponse>("/cleaning/requests", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const cancelCleaningRequest = (id: number, reason?: string) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/cancel`, {
    method: "POST",
    body: reason === undefined ? undefined : JSON.stringify({ reason }),
  });

export const takeBackRequest = (
  id: number,
  body: { reason: string; lock_version: number; worker_id?: number },
) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/reassign`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const requestStep = (
  id: number,
  step: RequestStep,
  body?: Record<string, string | number | undefined>,
  method = "POST",
) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/${step}`, {
    method,
    body: body && JSON.stringify(body),
  });

export function requestListPath(filters: RequestFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.status?.length) params.set("status", filters.status.join(","));
  if (filters.priority?.length)
    params.set("priority", filters.priority.join(","));
  if (filters.floor !== undefined) params.set("floor", String(filters.floor));
  if (filters.page && filters.page > 1)
    params.set("page", String(filters.page));
  if (filters.per_page) params.set("per_page", String(filters.per_page));
  const query = params.toString();
  return query ? `/cleaning/requests?${query}` : "/cleaning/requests";
}

export const fetchRequests = (filters: RequestFilters = {}) =>
  apiFetch<RequestPage>(requestListPath(filters));

export const fetchRequest = (id: number) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}`);

export const approveRequest = (id: number) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/approve`, {
    method: "POST",
  });

export const changeRequest = (id: number, body: RequestChange) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const fetchBoard = () => apiFetch<Board>("/cleaning/board");
