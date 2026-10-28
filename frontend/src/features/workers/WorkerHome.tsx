import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchMyProfile } from "../../api/profile";
import { fetchOffers } from "../../api/workers";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { Worker } from "../../types/worker";
import { WorkerDetails } from "../profile/ProfilePage";
import { LocationForm } from "./LocationForm";
import { OfferCard } from "./OfferCard";

export function WorkerHome() {
  const { data, error } = useQuery({
    queryKey: ["me", "profile"],
    queryFn: fetchMyProfile,
  });
  const offers = useQuery({
    queryKey: ["worker", "offers"],
    queryFn: fetchOffers,
    refetchInterval: 15_000,
  }).data?.offers;

  if (error)
    return (
      <ErrorMessage error={error} fallback="Could not load your status." />
    );
  if (!data) return <p className="page-loading">Loading…</p>;
  const profile = data.profile as Worker;
  return (
    <div className="stack">
      <h1>Home</h1>
      {offers?.map((offer) => (
        <OfferCard key={offer.id} offer={offer} />
      ))}
      {offers?.length === 0 && <p className="muted">No offers right now.</p>}
      <section className="card">
        <h2>Your tasks</h2>
        {profile.tasks.map((task) => (
          <p key={task.id}>
            <Link to={`/requests/${task.id}`}>Room {task.room}</Link> ·{" "}
            {task.status}
          </p>
        ))}
        {profile.tasks.length === 0 && (
          <p className="muted">No accepted tasks.</p>
        )}
      </section>
      <WorkerDetails profile={profile} />
      <section className="card">
        <h2>Update location</h2>
        <LocationForm workerId="me" />
      </section>
    </div>
  );
}
