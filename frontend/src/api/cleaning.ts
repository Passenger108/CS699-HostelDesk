import type {
  CleaningRequest,
  NewCleaningRequest,
  RequestFilters,
  RequestPage,
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

export const cancelCleaningRequest = (id: number) =>
  apiFetch<RequestResponse>(`/cleaning/requests/${id}/cancel`, {
    method: "POST",
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
