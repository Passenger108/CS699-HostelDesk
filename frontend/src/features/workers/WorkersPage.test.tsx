import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderSignedIn } from "../../test/renderApp";
import { submittedRequest } from "../cleaning/fixtures";
import { supervisorMe } from "../notifications/fixtures";

const floor2 = { id: 12, label: "Floor 2, Wing B" };
const note = "Updated 45 min ago, may be out of date";
const profile = {
  employee_id: "W01",
  last_location: floor2,
  location_note: note,
};
const worker = { ...profile, id: 2, name: "Ravi", tasks: [] };
const common = {
  "/notifications/unread-count": { unread_count: 0 },
  "/hostel/locations": { locations: [floor2] },
  "/workers": { workers: [worker] },
};

function sentBody(method: string) {
  const call = vi
    .mocked(fetch)
    .mock.calls.find(([, init]) => init?.method === method);
  return [String(call?.[0]), JSON.parse(String(call?.[1]?.body))];
}

describe("Worker location and offers", () => {
  it("lets a worker update their location from Home", async () => {
    mockApi({
      ...common,
      "/me": { user: { ...supervisorMe.user, role: "WORKER" }, profile },
    });
    renderSignedIn("/");
    expect(await screen.findByText(note)).toBeInTheDocument();
    await userEvent.selectOptions(
      await screen.findByLabelText("Floor and wing"),
      "12",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Update location" }),
    );
    expect(sentBody("PATCH")).toEqual([
      "/api/v1/workers/me/location",
      { location_id: 12, reason: "" },
    ]);
  });

  it("lets a supervisor correct a location with a reason", async () => {
    mockApi({ ...common, "/me": supervisorMe });
    renderSignedIn("/workers");
    expect(await screen.findByText(/Ravi/)).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Correct location" }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Floor and wing"),
      "12",
    );
    await userEvent.type(screen.getByLabelText("Reason"), "Phoned him");
    await userEvent.click(
      screen.getByRole("button", { name: "Update location" }),
    );
    expect(sentBody("PATCH")).toEqual([
      "/api/v1/workers/2/location",
      { location_id: 12, reason: "Phoned him" },
    ]);
  });

  it("sends an offer to a recommended worker", async () => {
    const request = {
      ...submittedRequest,
      status: "AWAITING_ASSIGNMENT",
      actions: ["offer"],
    };
    const reason = "Available on the same floor (Floor 2, Wing B).";
    mockApi({
      ...common,
      "/me": supervisorMe,
      "/cleaning/board": {
        generated_at: request.created_at,
        groups: [{ key: "new", label: "New", requests: [request] }],
      },
      "/cleaning/requests/7": { request },
      "/cleaning/requests/7/recommendations": {
        recommendations: [
          { worker, tier: 1, reason, warnings: ["Location is 45 min old."] },
        ],
      },
    });
    renderSignedIn("/");
    await userEvent.click(
      await screen.findByRole("button", { name: /Room A105/ }),
    );
    const send = await screen.findByRole("button", { name: "Send offer" });
    expect(send).toBeDisabled();
    await userEvent.click(await screen.findByRole("radio", { name: /Ravi/ }));
    expect(screen.getByText("Location is 45 min old.")).toBeInTheDocument();
    await userEvent.click(send);
    expect(sentBody("POST")).toEqual([
      "/api/v1/cleaning/requests/7/offers",
      { worker_id: 2, lock_version: 1 },
    ]);
  });
});
