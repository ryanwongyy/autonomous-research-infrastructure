import { memo } from "react";

export const RankChange = memo(function RankChange({ change }: { change: number }) {
  if (change === 0) return <span className="text-muted-foreground">&mdash;</span>;

  if (change > 0) {
    return <span className="text-green-600 dark:text-green-400">+{change}</span>;
  }

  return <span className="text-red-600 dark:text-red-400">{change}</span>;
});
