export type ReportRow = Record<string, string | number | null>;

export interface Column {
  key: string;
  label: string;
}

export interface CleaningReport {
  month: string;
  label: string;
  first_month: string;
  columns: { days: Column[]; workers: Column[] };
  totals: ReportRow;
  days: ReportRow[];
  workers: ReportRow[];
}

export type ReportTable = "days" | "workers";
