import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { fetchUnreadCount } from "../../api/notifications";

export function NotificationBell() {
  const { data } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: fetchUnreadCount,
    refetchInterval: 30_000,
  });
  const count = data?.unread_count ?? 0;
  const label =
    count === 1 ? "1 unread notification" : `${count} unread notifications`;

  return (
    <NavLink
      to="/notifications"
      className="bell"
      aria-label={`Notifications, ${label}`}
    >
      <span aria-hidden="true">Notifications</span>
      {count > 0 && (
        <span className="bell__count" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </NavLink>
  );
}
