import { useQuery } from '@tanstack/react-query';
import { fetchHostelStructure } from '../../api/hostel';
import { ErrorMessage } from '../../components/ErrorMessage';
import type { FloorNode } from '../../types/hostel';

function roomCount(floor: FloorNode) {
  return floor.wings.reduce((total, wing) => total + wing.rooms.length, 0);
}

function FloorSection({ floor }: { floor: FloorNode }) {
  const summary =
    floor.number === 0
      ? `${floor.facilities.length} service areas`
      : `${floor.wings.length} wings · ${roomCount(floor)} rooms`;

  return (
    <details className="card floor">
      <summary>
        <span className="floor__name">{floor.label}</span>
        <span className="muted">{summary}</span>
      </summary>
      {floor.facilities.length > 0 && (
        <ul className="room-list">
          {floor.facilities.map((facility) => (
            <li key={facility.id} className="chip">
              {facility.facility_name}
            </li>
          ))}
        </ul>
      )}
      {floor.wings.map((wing) => (
        <div key={wing.id} className="wing">
          <h3>Wing {wing.code}</h3>
          <ul className="room-list" aria-label={`${floor.label}, Wing ${wing.code} rooms`}>
            {wing.rooms.map((room) => (
              <li key={room.id} className="chip">
                {room.number}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </details>
  );
}

export function HostelStructurePage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['hostel', 'structure'],
    queryFn: fetchHostelStructure,
  });

  if (isPending) return <p className="page-loading">Loading…</p>;
  if (isError) return <ErrorMessage error={error} fallback="Could not load the hostel structure." />;

  const residential = data.floors.filter((floor) => floor.number > 0);
  const rooms = data.floors.reduce((total, floor) => total + roomCount(floor), 0);

  return (
    <div className="stack">
      <h1>{data.name} structure</h1>
      <p className="muted">
        {residential.length} residential floors · {rooms} rooms · read only
      </p>
      {data.floors.map((floor) => (
        <FloorSection key={floor.id} floor={floor} />
      ))}
    </div>
  );
}
