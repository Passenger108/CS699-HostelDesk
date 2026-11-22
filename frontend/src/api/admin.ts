import type { AuditFilters, AuditPage } from "../types/audit";
import type { Account, AccountStatus, NewAccount } from "../types/user";
import { apiFetch } from "./client";

type AccountResponse = { user: Account };

export const fetchAccounts = () =>
  apiFetch<{ users: Account[] }>("/admin/users");

export const createAccount = (body: NewAccount) =>
  apiFetch<AccountResponse>("/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const setAccountStatus = (id: number, account_status: AccountStatus) =>
  apiFetch<AccountResponse>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ account_status }),
  });

export function fetchAudit(filters: AuditFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && String(value).trim() !== "")
      params.set(key, String(value).trim());
  });
  return apiFetch<AuditPage>(`/admin/audit-logs?${params}`);
}
