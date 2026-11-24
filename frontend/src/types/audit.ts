import type { Person } from "./cleaning";

export interface AuditEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string;
  actor: Person | null;
  reason: string | null;
  created_at: string;
}

export interface AuditPage {
  entries: AuditEntry[];
  first_day: string;
  page: number;
  per_page: number;
  total: number;
  actions: string[];
}

export interface AuditFilters {
  action?: string;
  actor?: string;
  request?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
}
