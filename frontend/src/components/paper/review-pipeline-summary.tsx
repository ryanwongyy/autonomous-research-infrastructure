interface ReviewDot {
  id: number;
  stage: string;
  verdict: string;
}

interface ReviewPipelineSummaryProps {
  reviews: ReviewDot[];
}

const stageLabels: Record<string, string> = {
  l1_structure: "L1 Structural",
  l2_provenance: "L2 Provenance",
  l3_method: "L3 Method",
  l4_adversarial: "L4 Adversarial",
  l5_human: "L5 Human",
};

export function ReviewPipelineSummary({ reviews }: ReviewPipelineSummaryProps) {
  if (reviews.length === 0) return null;

  const passed = reviews.filter((r) => r.verdict === "pass").length;

  return (
    <div className="flex items-center gap-3 mb-4 text-sm">
      <div className="flex items-center gap-1.5" role="img" aria-label={`${passed} of ${reviews.length} review layers passed`}>
        {reviews.map((r) => (
          <span
            key={r.id}
            title={`${stageLabels[r.stage] ?? r.stage.replace(/_/g, " ")} — ${r.verdict}`}
            className={`inline-block h-3 w-3 rounded-full ${
              r.verdict === "pass"
                ? "bg-emerald-500 dark:bg-emerald-400"
                : r.verdict === "fail"
                ? "bg-red-500 dark:bg-red-400"
                : "bg-amber-500 dark:bg-amber-400"
            }`}
            aria-hidden="true"
          />
        ))}
      </div>
      <span className="text-muted-foreground">
        {passed} of {reviews.length} layers passed
      </span>
    </div>
  );
}
