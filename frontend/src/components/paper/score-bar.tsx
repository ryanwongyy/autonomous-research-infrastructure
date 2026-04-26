import { cn } from "@/lib/utils";

interface ScoreBarProps {
  score: number;
  max: number;
  label: string;
  /** Tailwind bg color class for the filled bar, e.g. "bg-blue-500" */
  color?: string;
  /** Show numeric value to right of bar */
  showValue?: boolean;
}

export function ScoreBar({
  score,
  max,
  label,
  color = "bg-primary",
  showValue = true,
}: ScoreBarProps) {
  const pct = max > 0 ? Math.min((score / max) * 100, 100) : 0;

  return (
    <div className="flex items-center gap-3">
      <span className="w-28 sm:w-36 text-xs sm:text-sm text-muted-foreground truncate">
        {label}
      </span>
      <div
        className="flex-1 h-2 bg-muted rounded-full overflow-hidden"
        role="meter"
        aria-label={label}
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showValue && (
        <span className="w-10 text-right text-xs font-mono font-semibold text-foreground">
          {score.toFixed(1)}
        </span>
      )}
    </div>
  );
}
