import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderSignedIn } from "../../test/renderApp";
import type { RequestSummary } from "../../types/cleaning";
import { studentMe, submittedRequest } from "./fixtures";

const summary: RequestSummary = {
  id: 7,
  status: "CANCELLED_BY_STUDENT",
  status_label: "Cancelled by you",
  is_active: false,
  priority: "URGENT",
  room: { id: 5, number: "A105", floor: 1, floor_label: "Floor 1", wing: "A" },
  availability_mode: "ANY_TIME_TODAY",
  credit_reservation: "RELEASED",
  student: { id: 1, name: "Demo Student", role: "STUDENT" },
  assigned_worker: null,
  created_at: "2026-10-19T04:30:00+00:00",
  closed_at: "2026-10-19T05:00:00+00:00",
  resolution_reason: "Cancelled by the student",
};

function page(requests: RequestSummary[], pageNumber: number, total: number) {
  return { requests, page: pageNumber, per_page: 10, total };
}

describe("History", () => {
  it("lists own requests with status and dates", async () => {
    mockApi({
      "/me": studentMe,
      "/cleaning/requests?per_page=10": page([summary], 1, 1),
    });
    renderSignedIn("/history");

    const table = await screen.findByRole("table");
    const row = within(table).getAllByRole("row")[1];
    expect(within(row).getByText("Cancelled by you")).toBeInTheDocument();
    expect(within(row).getByText("Urgent")).toBeInTheDocument();
    expect(within(row).getByText("A105")).toBeInTheDocument();
    expect(within(row).getByRole("link")).toHaveAttribute(
      "href",
      "/requests/7",
    );
  });

  it("says so when there is no history", async () => {
    mockApi({
      "/me": studentMe,
      "/cleaning/requests?per_page=10": page([], 1, 0),
    });
    renderSignedIn("/history");
    expect(
      await screen.findByText("You have not asked for cleaning yet."),
    ).toBeInTheDocument();
  });

  it("moves between pages", async () => {
    const older = {
      ...summary,
      id: 6,
      created_at: "2026-10-18T04:30:00+00:00",
    };
    mockApi({
      "/me": studentMe,
      "/cleaning/requests?per_page=10": page([summary], 1, 11),
      "/cleaning/requests?page=2&per_page=10": page([older], 2, 11),
    });
    renderSignedIn("/history");

    expect(await screen.findByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Newer" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Older" }));
    expect(await screen.findByText("Page 2 of 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /18 Oct 2026/ })).toHaveAttribute(
      "href",
      "/requests/6",
    );
  });

  it("opens a request with its timeline", async () => {
    mockApi({
      "/me": studentMe,
      "/cleaning/requests/7": { request: submittedRequest },
    });
    renderSignedIn("/requests/7");
    expect(
      await screen.findByText("Waiting for supervisor approval"),
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Timeline" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancel request" }),
    ).toBeInTheDocument();
  });

  it("shows the server message for a request that is not yours", async () => {
    mockApi(
      { "/me": studentMe },
      {
        "/cleaning/requests/99": [
          404,
          "REQUEST_NOT_FOUND",
          "This request does not exist.",
        ],
      },
    );
    renderSignedIn("/requests/99");
    expect(
      await screen.findByText("This request does not exist."),
    ).toBeInTheDocument();
  });
});
