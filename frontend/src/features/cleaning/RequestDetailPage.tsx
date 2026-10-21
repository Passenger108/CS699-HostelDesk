import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchRequest } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import { NotFoundPage } from "../../pages/NotFoundPage";
import { RequestDetails } from "./ActiveRequestCard";

export function RequestDetailPage() {
  const { requestId } = useParams();
  const id = Number(requestId);
  const valid = Number.isInteger(id) && id > 0;
  const { data, isPending, error } = useQuery({
    queryKey: ["cleaning", "request", id],
    queryFn: () => fetchRequest(id),
    enabled: valid,
  });

  if (!valid) return <NotFoundPage />;
  if (isPending) return <p className="page-loading">Loading…</p>;
  if (error)
    return (
      <ErrorMessage error={error} fallback="Could not load this request." />
    );

  const request = data.request;
  return (
    <section className="card request-card">
      <h1>Cleaning request</h1>
      <p className="muted">
        Request {request.id} · {request.student.name}
      </p>
      <RequestDetails request={request} />
      <Link to="/">Back to Home</Link>
    </section>
  );
}
