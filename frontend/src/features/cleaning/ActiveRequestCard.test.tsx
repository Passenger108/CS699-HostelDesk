import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderSignedIn } from "../../test/renderApp";
import { creditsWith, studentMe, submittedRequest } from "./fixtures";

describe("Active request card", () => {
  it("offers to request cleaning when nothing is active", async () => {
    mockApi({
      "/me": studentMe,
      "/me/credits": creditsWith(1),
      "/cleaning/requests/active": { request: null },
    });
    renderSignedIn("/");
    expect(
      await screen.findByText("You have no active cleaning request."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request cleaning" }),
    ).toHaveAttribute("href", "/request");
  });

  it("shows status, details and timeline", async () => {
    mockApi({
      "/me": studentMe,
      "/me/credits": creditsWith(0),
      "/cleaning/requests/active": {
        request: { ...submittedRequest, eta_label: "Ravi, by 10:16 am" },
      },
    });
    renderSignedIn("/");

    expect(
      await screen.findByText("Waiting for supervisor approval"),
    ).toBeInTheDocument();
    expect(screen.getByText("Ravi, by 10:16 am")).toBeInTheDocument();
    expect(screen.getByText("A105 · Floor 1, Wing A")).toBeInTheDocument();
    expect(screen.getByText("Today, 2:00 pm to 3:30 pm")).toBeInTheDocument();
    expect(screen.getByText("1 reserved")).toBeInTheDocument();
    expect(screen.getByText("“Please clean the balcony”")).toBeInTheDocument();
    const timeline = screen.getByRole("list", { name: "Timeline" });
    expect(within(timeline).getByText("Request submitted")).toBeInTheDocument();
  });

  it("cancels after confirming", async () => {
    const cancelled = {
      ...submittedRequest,
      status: "CANCELLED_BY_STUDENT",
      is_active: false,
      actions: [],
    };
    const routes: Record<string, unknown> = {
      "/me": studentMe,
      "/me/credits": creditsWith(0),
      "/cleaning/requests/active": { request: submittedRequest },
      "/cleaning/requests/7/cancel": { request: cancelled },
    };
    mockApi(routes);
    renderSignedIn("/");

    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel request" }),
    );
    expect(
      screen.getByText(/Your credit will be returned/),
    ).toBeInTheDocument();
    routes["/cleaning/requests/active"] = { request: null };
    routes["/me/credits"] = creditsWith(1);
    await userEvent.click(screen.getByRole("button", { name: "Yes, cancel" }));

    expect(
      await screen.findByText("You have no active cleaning request."),
    ).toBeInTheDocument();
    const cancelCall = vi
      .mocked(fetch)
      .mock.calls.find(([url]) =>
        String(url).endsWith("/cleaning/requests/7/cancel"),
      );
    expect(cancelCall?.[1]?.method).toBe("POST");
  });

  it("can keep the request instead", async () => {
    mockApi({
      "/me": studentMe,
      "/me/credits": creditsWith(0),
      "/cleaning/requests/active": { request: submittedRequest },
    });
    renderSignedIn("/");
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel request" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Keep request" }));
    expect(
      screen.getByRole("button", { name: "Cancel request" }),
    ).toBeInTheDocument();
  });
});
