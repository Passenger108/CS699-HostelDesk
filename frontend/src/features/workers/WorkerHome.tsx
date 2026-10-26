import { useQuery } from "@tanstack/react-query";
import { fetchMyProfile } from "../../api/profile";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { WorkerProfile } from "../../types/profile";
import { WorkerDetails } from "../profile/ProfilePage";
import { LocationForm } from "./LocationForm";

export function WorkerHome() {
  const { data, error } = useQuery({
    queryKey: ["me", "profile"],
    queryFn: fetchMyProfile,
  });

  if (error)
    return (
      <ErrorMessage error={error} fallback="Could not load your status." />
    );
  if (!data) return <p className="page-loading">Loading…</p>;
  const profile = data.profile as WorkerProfile;
  return (
    <div className="stack">
      <h1>Home</h1>
      <WorkerDetails profile={profile} />
      <section className="card">
        <h2>Update location</h2>
        <LocationForm workerId="me" />
      </section>
    </div>
  );
}
