import type { RequestEvent } from '../../types/cleaning';
import { formatDateTime } from '../../utils/format';

export function RequestTimeline({ events }: { events: RequestEvent[] }) {
  return (
    <ol className="timeline" aria-label="Timeline">
      {events.map((event) => (
        <li key={event.id} className="timeline__item">
          <span className="timeline__label">{event.label}</span>
          <span className="muted timeline__meta">
            {formatDateTime(event.occurred_at)}
            {event.actor ? ` · ${event.actor.name}` : ' · System'}
          </span>
        </li>
      ))}
    </ol>
  );
}
