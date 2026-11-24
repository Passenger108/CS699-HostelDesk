export type CreditEntryType =
  | 'WEEKLY_GRANT'
  | 'WEEKLY_CAPPED'
  | 'GOODWILL_GRANT'
  | 'RESERVE'
  | 'RELEASE'
  | 'CONSUME'
  | 'EXPIRE';

export interface CreditBalance {
  available: number;
  standard_available: number;
  goodwill_available: number;
  reserved: number;
  consumed: number;
  cap: number;
  next_grant_at: string;
}

export interface CreditEntry {
  id: number;
  entry_type: CreditEntryType;
  credit_type: 'STANDARD' | 'GOODWILL';
  quantity: number;
  reason: string;
  request_id: number | null;
  created_at: string;
  expires_at: string | null;
  grant_week: string | null;
}

export interface MyCredits {
  balance: CreditBalance;
  history: CreditEntry[];
}
