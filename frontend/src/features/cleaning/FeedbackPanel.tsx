import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { rateCleaning } from "../../api/cleaning";
import { ErrorMessage } from "../../components/ErrorMessage";
import type { CleaningRequest } from "../../types/cleaning";

const STARS = [1, 2, 3, 4, 5];

export function Stars({ rating }: { rating: number }) {
  return (
    <span className="stars" aria-label={`${rating} out of 5 stars`}>
      {"★".repeat(rating)}
      <span className="stars__empty">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

function RateForm({ request }: { request: CleaningRequest }) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const needsComment = rating > 0 && rating <= 2;
  const rate = useMutation({
    mutationFn: () => rateCleaning(request.id, rating, comment),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cleaning"] }),
  });

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        rate.mutate();
      }}
    >
      <fieldset className="choice-group">
        <legend>How was the cleaning?</legend>
        <div className="choice-row">
          {STARS.map((value) => (
            <button
              key={value}
              type="button"
              className={`star${value <= rating ? " star--on" : ""}`}
              aria-label={`${value} star${value > 1 ? "s" : ""}`}
              aria-pressed={value === rating}
              onClick={() => setRating(value)}
            >
              ★
            </button>
          ))}
        </div>
      </fieldset>
      <label className="text-field">
        {needsComment ? "What went wrong? (needed)" : "Comment (optional)"}
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={500}
          rows={2}
        />
      </label>
      <p className="muted">
        The worker sees your stars and comment without your name, room or date.
      </p>
      <div className="choice-row">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={
            rating === 0 || (needsComment && !comment.trim()) || rate.isPending
          }
        >
          {rate.isPending ? "Sending…" : "Send rating"}
        </button>
      </div>
      {rate.isError && (
        <ErrorMessage error={rate.error} fallback="Could not send. Try again." />
      )}
    </form>
  );
}

export function FeedbackPanel({ request }: { request: CleaningRequest }) {
  const feedback = request.feedback;
  if (!feedback) return null;
  return (
    <section aria-label="Feedback">
      <h3>Feedback</h3>
      <p className="muted">
        {feedback.label}{" "}
        {feedback.rating !== null && <Stars rating={feedback.rating} />}
      </p>
      {feedback.comment && (
        <p className="request-card__note">“{feedback.comment}”</p>
      )}
      {request.actions.includes("rate") && <RateForm request={request} />}
    </section>
  );
}
