import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderSignedIn } from "../../test/renderApp";
import { submittedRequest } from "../cleaning/fixtures";
import { newRequestNotice, oldNotice, supervisorMe } from "./fixtures";

function calls(suffix: string, method: string) {
  return vi
    .mocked(fetch)
    .mock.calls.filter(
      ([url, init]) =>
        String(url).endsWith(suffix) && (init?.method ?? "GET") === method,
    );
}

describe("Notification centre", () => {
  it("shows the unread count on the bell", async () => {
    mockApi({
      "/me": supervisorMe,
      "/notifications/unread-count": { unread_count: 2 },
    });
    renderSignedIn("/notifications");
    expect(
      await screen.findByRole("link", {
        name: "Notifications, 2 unread notifications",
      }),
    ).toBeInTheDocument();
  });

  it("lists notifications newest first with read state", async () => {
    mockApi({
      "/me": supervisorMe,
      "/notifications/unread-count": { unread_count: 1 },
      "/notifications": {
        notifications: [newRequestNotice, oldNotice],
        unread_count: 1,
      },
    });
    renderSignedIn("/notifications");

    const items = await screen.findAllByRole("listitem");
    expect(
      within(items[0]).getByText("New cleaning request"),
    ).toBeInTheDocument();
    expect(
      within(items[0]).getByText("Room A105 asked for cleaning."),
    ).toBeInTheDocument();
    expect(
      within(items[0]).getByRole("button", { name: "Mark as read" }),
    ).toBeInTheDocument();
    expect(
      within(items[1]).getByRole("button", { name: "Mark as unread" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Unread (1)" }),
    ).toBeInTheDocument();
  });

  it("marks a notification as read", async () => {
    const routes: Record<string, unknown> = {
      "/me": supervisorMe,
      "/notifications/unread-count": { unread_count: 1 },
      "/notifications": { notifications: [newRequestNotice], unread_count: 1 },
      "/notifications/11/read": {
        notification: { ...newRequestNotice, is_read: true },
        unread_count: 0,
      },
    };
    mockApi(routes);
    renderSignedIn("/notifications");

    const button = await screen.findByRole("button", { name: "Mark as read" });
    routes["/notifications"] = {
      notifications: [{ ...newRequestNotice, is_read: true }],
      unread_count: 0,
    };
    routes["/notifications/unread-count"] = { unread_count: 0 };
    await userEvent.click(button);

    expect(
      await screen.findByRole("button", { name: "Mark as unread" }),
    ).toBeInTheDocument();
    expect(calls("/notifications/11/read", "PATCH")).toHaveLength(1);
    expect(
      await screen.findByRole("link", {
        name: "Notifications, 0 unread notifications",
      }),
    ).toBeInTheDocument();
  });

  it("opens the request and marks it read", async () => {
    mockApi({
      "/me": supervisorMe,
      "/notifications/unread-count": { unread_count: 1 },
      "/notifications": { notifications: [newRequestNotice], unread_count: 1 },
      "/notifications/11/read": {
        notification: { ...newRequestNotice, is_read: true },
        unread_count: 0,
      },
      "/cleaning/requests/7": { request: { ...submittedRequest, actions: [] } },
    });
    renderSignedIn("/notifications");

    await userEvent.click(
      await screen.findByRole("button", { name: "Open request" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Cleaning request" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Waiting for supervisor approval"),
    ).toBeInTheDocument();
    expect(calls("/notifications/11/read", "PATCH")).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: "Cancel request" }),
    ).not.toBeInTheDocument();
  });

  it("shows an empty message", async () => {
    mockApi({
      "/me": supervisorMe,
      "/notifications/unread-count": { unread_count: 0 },
      "/notifications": { notifications: [], unread_count: 0 },
      "/notifications?unread=true": { notifications: [], unread_count: 0 },
    });
    renderSignedIn("/notifications");
    expect(
      await screen.findByText("You have no notifications yet."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Unread/ }));
    expect(
      await screen.findByText("You have no unread notifications."),
    ).toBeInTheDocument();
  });
});
