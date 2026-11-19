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
