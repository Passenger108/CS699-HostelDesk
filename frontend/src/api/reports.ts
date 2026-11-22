import type { CleaningReport, ReportTable } from "../types/report";
import { apiBlob, apiFetch } from "./client";

export const fetchReport = (month: string) =>
  apiFetch<CleaningReport>(`/reports/cleaning?month=${month}`);

export async function downloadReport(month: string, table: ReportTable) {
  const blob = await apiBlob(
    `/reports/cleaning.csv?month=${month}&table=${table}`,
  );
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `hosteldesk-cleaning-${month}-${table}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
}
