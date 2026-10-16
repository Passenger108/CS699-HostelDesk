import type { CreditEntryType } from '../../types/credits';

export const ENTRY_LABELS: Record<CreditEntryType, string> = {
  WEEKLY_GRANT: 'Weekly credit added',
  WEEKLY_CAPPED: 'Weekly credit not added (limit reached)',
  GOODWILL_GRANT: 'Goodwill credit from the supervisor',
  RESERVE: 'Reserved for a cleaning request',
  RELEASE: 'Returned to you',
  CONSUME: 'Used for a cleaning',
  EXPIRE: 'Goodwill credit expired',
};

export const ENTRY_SIGN: Record<CreditEntryType, string> = {
  WEEKLY_GRANT: '+1',
  WEEKLY_CAPPED: '0',
  GOODWILL_GRANT: '+1',
  RESERVE: '−1',
  RELEASE: '+1',
  CONSUME: '✓',
  EXPIRE: '−1',
};
