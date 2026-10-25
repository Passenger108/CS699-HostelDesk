import { SectionPage } from "../../pages/SectionPage";
import { useAuth } from "../auth/AuthContext";
import { ActiveRequestCard } from "../cleaning/ActiveRequestCard";
import { CreditsCard } from "../credits/CreditsCard";
import { OperationsPage } from "../operations/OperationsPage";
import { WorkerHome } from "../workers/WorkerHome";

function StudentHome() {
  return (
    <div className="stack">
      <h1>Home</h1>
      <ActiveRequestCard />
      <CreditsCard />
    </div>
  );
}

export function HomePage() {
  const { user } = useAuth();
  if (user?.role === "STUDENT") return <StudentHome />;
  if (user?.role === "WORKER") return <WorkerHome />;
  if (user?.role === "SUPERVISOR" || user?.role === "SUPER_ADMIN")
    return <OperationsPage />;
  return <SectionPage />;
}
