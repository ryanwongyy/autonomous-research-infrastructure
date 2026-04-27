import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { AutonomyCard } from "@/lib/types";

const autonomyColors: Record<string, string> = {
  full: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  high: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  moderate: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  supervised: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export function AutonomyCardSection({ card }: { card: AutonomyCard }) {
  const scoreColor =
    card.overall_autonomy_score >= 0.8
      ? "text-emerald-600 dark:text-emerald-400"
      : card.overall_autonomy_score >= 0.5
      ? "text-amber-600 dark:text-amber-400"
      : "text-red-600 dark:text-red-400";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Autonomy Breakdown</CardTitle>
          <div className="text-right">
            <span className={`text-2xl font-bold font-mono ${scoreColor}`}>
              {(card.overall_autonomy_score * 100).toFixed(0)}%
            </span>
            <div className="text-[11px] text-muted-foreground">Overall autonomy</div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs text-muted-foreground mb-2">Autonomy by role</p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(card.role_autonomy).map(([role, level]) => (
              <div key={role} className="flex items-center justify-between rounded-md border px-2.5 py-1.5">
                <span className="text-xs font-medium capitalize truncate">
                  {role.replace(/_/g, " ")}
                </span>
                <Badge
                  variant="secondary"
                  className={`text-[11px] ${autonomyColors[level.toLowerCase()] ?? ""}`}
                >
                  {level}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        {card.human_intervention_points.length > 0 && (
          <div className="border-t pt-3">
            <p className="text-xs text-muted-foreground mb-2">Human intervention points</p>
            <ul className="space-y-1.5">
              {card.human_intervention_points.map((point, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500 dark:bg-amber-400" />
                  <span>
                    <strong className="text-foreground capitalize">{point.role.replace(/_/g, " ")}</strong>
                    {" "}({point.level}): {point.description}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
