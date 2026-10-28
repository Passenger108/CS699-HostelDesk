import type { CleaningRequest } from "../types/cleaning";
import type { LocationInfo } from "../types/hostel";
import type { Recommendation, Worker, WorkerOffer } from "../types/worker";
import { apiFetch } from "./client";

export const fetchWorkers = () => apiFetch<{ workers: Worker[] }>("/workers");

export const fetchLocations = () =>
  apiFetch<{ locations: LocationInfo[] }>("/hostel/locations");

export const moveWorker = (
  id: number | "me",
  location_id: number,
  reason: string,
) =>
  apiFetch<{ worker: Worker }>(`/workers/${id}/location`, {
    method: "PATCH",
    body: JSON.stringify({ location_id, reason }),
  });

export const fetchRecommendations = (id: number) =>
  apiFetch<{ recommendations: Recommendation[] }>(
    `/cleaning/requests/${id}/recommendations`,
  );

export const sendOffer = (
  id: number,
  worker_id: number,
  lock_version: number,
) =>
  apiFetch<{ request: CleaningRequest }>(`/cleaning/requests/${id}/offers`, {
    method: "POST",
    body: JSON.stringify({ worker_id, lock_version }),
  });

export const fetchOffers = () =>
  apiFetch<{ offers: WorkerOffer[] }>("/worker/offers");

export const answerOffer = (
  id: number,
  answer: "accept" | "decline",
  body: { eta_minutes: number } | { reason: string },
) =>
  apiFetch<{ request: CleaningRequest }>(`/worker/offers/${id}/${answer}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
