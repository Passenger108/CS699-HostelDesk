import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { fetchProof } from "../../api/cleaning";
import type { Completion } from "../../types/cleaning";

export function ProofImage({ completion }: { completion: Completion }) {
  const path = completion.proof_url;
  const { data, isError } = useQuery({
    queryKey: ["cleaning", "proof", path, completion.proof_added_at],
    queryFn: () => fetchProof(path as string),
    enabled: Boolean(path),
    staleTime: Infinity,
  });
  const src = useMemo(() => (data ? URL.createObjectURL(data) : null), [data]);
  useEffect(
    () => () => {
      if (src) URL.revokeObjectURL(src);
    },
    [src],
  );

  if (!path) return null;
  if (isError) return <p className="muted">Could not load the photo.</p>;
  if (!src) return <p className="muted">Loading photo…</p>;
  return (
    <figure className="proof">
      <img src={src} alt="Photo of the cleaned room with the server stamp" />
      <figcaption className="muted">
        Stamped by HostelDesk with the room and server time.
      </figcaption>
    </figure>
  );
}
