import { useQuery } from "@tanstack/react-query";
import { fetchMyFeedback } from "../../api/workers";
import type { RatingSummary } from "../../types/worker";
import { Stars } from "../cleaning/FeedbackPanel";

export function ratingText(rating: RatingSummary) {
  if (rating.average === null) return "No ratings yet";
  return `${rating.average} of 5 from ${rating.count} rating${rating.count > 1 ? "s" : ""}`;
}

export function MyRatings() {
  const { data } = useQuery({
    queryKey: ["workers", "me", "feedback"],
    queryFn: fetchMyFeedback,
  });
  if (!data) return null;
  const feedback = data.feedback;
  return (
    <section className="card stack">
      <h2>Your ratings</h2>
      <p>
        {feedback.average !== null && (
          <Stars rating={Math.round(feedback.average)} />
        )}{" "}
        {ratingText(feedback)}
      </p>
      {feedback.comments.length > 0 && (
        <ul className="notice-list">
          {feedback.comments.map((comment, index) => (
            <li key={index} className="notice">
              “{comment}”
            </li>
          ))}
        </ul>
      )}
      <p className="muted">
        Students rate anonymously, so you never see who wrote what or when.
      </p>
    </section>
  );
}
