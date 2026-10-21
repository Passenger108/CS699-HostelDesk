import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

function mockFetch(
  handler: (url: string, init?: RequestInit) => [number, unknown],
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const [status, body] = handler(String(input), init);
    return new Response(JSON.stringify(body), { status });
  });
}

const supervisor = {
  id: 3,
  role: "SUPERVISOR",
  login_id: "demo.supervisor",
  name: "Demo Supervisor",
  phone: null,
  email: null,
  locale: "en",
  account_status: "ACTIVE",
};

describe("App shell", () => {
  beforeEach(() => window.history.pushState({}, "", "/"));

  it("sends signed-out users to the login page", async () => {
    render(<App />);
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
  });

  it("signs in and shows the navigation for the user role", async () => {
    mockFetch(() => [
      200,
      { access_token: "a", refresh_token: "r", user: supervisor },
    ]);
    render(<App />);

    await userEvent.type(
      await screen.findByLabelText("Login ID"),
      "demo.supervisor",
    );
    await userEvent.type(
      screen.getByLabelText("Password"),
      "hosteldesk-demo-2026",
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const nav = await screen.findByRole("navigation", { name: "Primary" });
    expect(nav).toHaveTextContent("Operations");
    expect(nav).toHaveTextContent("Workers");
    expect(nav).not.toHaveTextContent("Audit");
    expect(screen.getByText("Supervisor")).toBeInTheDocument();
  });

  it("shows the server error message on a failed sign in", async () => {
    mockFetch(() => [
      401,
      {
        error: {
          code: "INVALID_CREDENTIALS",
          message: "Invalid login ID or password.",
        },
      },
    ]);
    render(<App />);

    await userEvent.type(await screen.findByLabelText("Login ID"), "someone");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid login ID or password.",
    );
  });

  it("hides pages that are not in the role navigation", async () => {
    localStorage.setItem(
      "hosteldesk.session",
      JSON.stringify({ accessToken: "a", refreshToken: "r" }),
    );
    mockFetch(() => [200, { user: supervisor }]);
    window.history.pushState({}, "", "/audit");
    render(<App />);
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
  });

  it("opens Home when the page asked for belongs to another role", async () => {
    mockFetch((url) =>
      url.endsWith("/auth/login")
        ? [200, { access_token: "a", refresh_token: "r", user: supervisor }]
        : [200, { unread_count: 0 }],
    );
    window.history.pushState({}, "", "/credits");
    render(<App />);

    await userEvent.type(
      await screen.findByLabelText("Login ID"),
      "demo.supervisor",
    );
    await userEvent.type(
      screen.getByLabelText("Password"),
      "hosteldesk-demo-2026",
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("navigation", { name: "Primary" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
    expect(screen.queryByText("Page not found")).not.toBeInTheDocument();
  });

  it("offers a retry instead of signing out when the server cannot be reached", async () => {
    localStorage.setItem(
      "hosteldesk.session",
      JSON.stringify({ accessToken: "a", refreshToken: "r" }),
    );
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new TypeError("Failed to fetch"),
    );
    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach HostelDesk",
    );
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
    expect(localStorage.getItem("hosteldesk.session")).not.toBeNull();
  });
});
