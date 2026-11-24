import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchNotifications,
  markNotificationRead,
  markNotificationUnread,
} from "../../api/notifications";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { AppNotification } from "../../types/notification";
import { formatDateTime } from "../../utils/format";

function NotificationItem({ item }: { item: AppNotification }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toggle = useMutation({
    mutationFn: (read: boolean) =>
      read ? markNotificationRead(item.id) : markNotificationUnread(item.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  function open() {
    const go = () =>
      item.request_id && navigate(`/requests/${item.request_id}`);
    if (item.is_read) go();
    else toggle.mutate(true, { onSuccess: go });
  }

  return (
    <li className={`notice${item.is_read ? "" : " notice--unread"}`}>
      <div className="notice__text">
        <strong>{item.title}</strong>
        <p>{item.body}</p>
        <span className="muted">{formatDateTime(item.created_at)}</span>
      </div>
      <div className="notice__buttons">
        {item.request_id !== null && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={open}
            disabled={toggle.isPending}
          >
            Open request
          </button>
        )}
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => toggle.mutate(!item.is_read)}
          disabled={toggle.isPending}
        >
          {item.is_read ? "Mark as unread" : "Mark as read"}
        </button>
      </div>
      {toggle.isError && (
        <ErrorMessage error={toggle.error} fallback="Could not update it." />
      )}
    </li>
  );
}

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const { data, isPending, error } = useQuery({
    queryKey: ["notifications", "list", unreadOnly],
    queryFn: () => fetchNotifications(unreadOnly),
    refetchInterval: 30_000,
  });

  return (
    <section className="stack">
      <h1>Notifications</h1>
      <div className="choice-row" role="group" aria-label="Show">
        <button
          type="button"
          className={`btn ${unreadOnly ? "btn--ghost" : "btn--primary"}`}
          aria-pressed={!unreadOnly}
          onClick={() => setUnreadOnly(false)}
        >
          All
        </button>
        <button
          type="button"
          className={`btn ${unreadOnly ? "btn--primary" : "btn--ghost"}`}
          aria-pressed={unreadOnly}
          onClick={() => setUnreadOnly(true)}
        >
          Unread{data ? ` (${data.unread_count})` : ""}
        </button>
      </div>
      {isPending && <p className="page-loading">Loading…</p>}
      {error && (
        <ErrorMessage
          error={error}
          fallback="Could not load your notifications."
        />
      )}
      {data && data.notifications.length === 0 && (
        <p className="card muted">
          {unreadOnly
            ? "You have no unread notifications."
            : "You have no notifications yet."}
        </p>
      )}
      {data && data.notifications.length > 0 && (
        <ul className="notice-list">
          {data.notifications.map((item) => (
            <NotificationItem key={item.id} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}
