export interface AppNotification {
  id: number;
  type: string;
  title: string;
  body: string;
  request_id: number | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationList {
  notifications: AppNotification[];
  unread_count: number;
}
