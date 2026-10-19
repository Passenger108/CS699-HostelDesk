import type { CleaningRequest } from '../../types/cleaning';
import { statusTone } from './labels';

export function StatusChip({ request }: { request: CleaningRequest }) {
  return (
    <span className={`status-chip status-chip--${statusTone(request.status)}`}>
      {request.status_label}
    </span>
  );
}
