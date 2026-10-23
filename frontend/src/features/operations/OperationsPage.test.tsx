import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderSignedIn } from "../../test/renderApp";
import { submittedRequest } from "../cleaning/fixtures";
import { supervisorMe } from "../notifications/fixtures";

const request = { ...submittedRequest, actions: ["approve", "change"] };
const board = {
  generated_at: "2026-10-17T05:25:00+00:00",
  groups: [
    { key: "urgent", label: "Urgent and emergency", requests: [] },
    { key: "new", label: "New, waiting for approval", requests: [request] },
  ],
};

function openBoard() {
  mockApi({
    "/me": supervisorMe,
    "/notifications/unread-count": { unread_count: 0 },
    "/cleaning/board": board,
    "/cleaning/requests/7": { request },
    "/cleaning/requests/7/approve": { request },
  });
  renderSignedIn("/");
}

function sent(method: string) {
  return vi
    .mocked(fetch)
    .mock.calls.filter(([, init]) => init?.method === method);
}

describe("Operations board", () => {
  it("shows each queue with its cards", async () => {
    openBoard();
    const queue = await screen.findByRole("region", {
      name: "New, waiting for approval",
    });
    expect(within(queue).getByText("Room A105")).toBeInTheDocument();
    expect(within(queue).getByText(/sent 25 min ago/)).toBeInTheDocument();
    const urgent = screen.getByRole("region", { name: "Urgent and emergency" });
    expect(within(urgent).getByText("None")).toBeInTheDocument();
  });

  it("approves from the request drawer", async () => {
    openBoard();
    await userEvent.click(
      await screen.findByRole("button", { name: /Room A105/ }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Approve" }),
    );
    expect(String(sent("POST")[0][0])).toContain(
      "/cleaning/requests/7/approve",
    );
  });

  it("changes the priority with a reason", async () => {
    openBoard();
    await userEvent.click(
      await screen.findByRole("button", { name: /Room A105/ }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Priority"),
      "URGENT",
    );
    await userEvent.type(screen.getByLabelText("Reason"), "Exam week");
    await userEvent.click(screen.getByRole("button", { name: "Save change" }));
    expect(JSON.parse(String(sent("PATCH")[0][1]?.body))).toEqual({
      lock_version: 1,
      reason: "Exam week",
      priority: "URGENT",
    });
  });
});
