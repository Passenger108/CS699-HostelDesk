import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createAccount,
  fetchAccounts,
  setAccountStatus,
} from "../../api/admin";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { Account, NewAccount, Role } from "../../types/user";
import { ROLE_LABELS } from "../../app/navigation";
import { useAuth } from "../auth/AuthContext";

type Field = [
  key: keyof NewAccount,
  label: string,
  placeholder: string,
  type?: string,
];

const COMMON: Field[] = [
  ["name", "Full name", "Riya Sharma (letters only)"],
  ["login_id", "Login ID", "riya.sharma (3 to 30: a-z, 0-9, . _ -)"],
  ["password", "First password", "At least 12 characters", "password"],
  ["phone", "Phone", "+91 98765 43210 (Indian mobile)", "tel"],
  ["email", "Email (optional)", "riya@example.com", "email"],
];
const BY_ROLE: Record<Role, Field[]> = {
  STUDENT: [
    ["roll_number", "Roll number", "24B0001"],
    ["room", "Room (at most 2 students)", "A105"],
  ],
  WORKER: [["employee_id", "Employee ID", "W04"]],
  SUPERVISOR: [],
  SUPER_ADMIN: [],
};
const EMPTY: NewAccount = {
  role: "STUDENT",
  login_id: "",
  name: "",
  password: "",
};

function NewAccountForm({ shifts }: { shifts: string[] }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<NewAccount>(EMPTY);
  const create = useMutation({
    mutationFn: () => createAccount(form),
    onSuccess: () => {
      setForm({ ...EMPTY, role: form.role });
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
  const fields = [...COMMON, ...BY_ROLE[form.role]];

  return (
    <form
      className="card stack"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <h2>Add a person</h2>
      <div className="form-grid">
        <label className="text-field">
          Role
          <select
            value={form.role}
            onChange={(e) =>
              setForm({ ...EMPTY, role: e.target.value as Role })
            }
          >
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {fields.map(([key, label, placeholder, type]) => (
          <label key={key} className="text-field">
            {label}
            <input
              type={type ?? "text"}
              placeholder={placeholder}
              value={form[key] ?? ""}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </label>
        ))}
        {form.role === "WORKER" && (
          <label className="text-field">
            Shift
            <select
              value={form.shift ?? ""}
              onChange={(e) => setForm({ ...form, shift: e.target.value })}
            >
              <option value="">Choose a shift</option>
              {shifts.map((shift) => (
                <option key={shift}>{shift}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="choice-row">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={create.isPending}
        >
          {create.isPending ? "Adding…" : "Add person"}
        </button>
      </div>
      {create.isSuccess && (
        <p role="status">
          Added {create.data.user.name}. They can log in as{" "}
          {create.data.user.login_id}.
        </p>
      )}
      {create.isError && (
        <ErrorMessage
          error={create.error}
          fallback="Could not add this person."
        />
      )}
    </form>
  );
}

function StatusButton({ account }: { account: Account }) {
  const queryClient = useQueryClient();
  const next = account.account_status === "ACTIVE" ? "DISABLED" : "ACTIVE";
  const change = useMutation({
    mutationFn: () => setAccountStatus(account.id, next),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
  return (
    <>
      <button
        type="button"
        className={
          next === "DISABLED"
            ? "btn btn--ghost btn--small"
            : "btn btn--primary btn--small"
        }
        disabled={change.isPending}
        onClick={() => change.mutate()}
      >
        {next === "DISABLED" ? "Disable" : "Enable"}
      </button>
      {change.isError && (
        <ErrorMessage
          error={change.error}
          fallback="Could not change this account."
        />
      )}
    </>
  );
}

export function PeoplePage() {
  const me = useAuth().user;
  const { data, isPending, error } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchAccounts,
  });

  return (
    <div className="stack">
      <h1>People</h1>
      <NewAccountForm shifts={data?.shifts ?? []} />
      {isPending && <p className="page-loading">Loading…</p>}
      {error && (
        <ErrorMessage error={error} fallback="Could not load people." />
      )}
      {data && (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Login ID</th>
                <th>Role</th>
                <th>Details</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.users.map((account) => (
                <tr key={account.id}>
                  <td>{account.name}</td>
                  <td>{account.login_id}</td>
                  <td>{account.role_label}</td>
                  <td>{account.detail ?? "—"}</td>
                  <td>
                    {account.account_status === "ACTIVE"
                      ? "Active"
                      : account.account_status === "DISABLED"
                        ? "Disabled"
                        : "Locked"}
                  </td>
                  <td>
                    {account.id !== me?.id && (
                      <StatusButton account={account} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
