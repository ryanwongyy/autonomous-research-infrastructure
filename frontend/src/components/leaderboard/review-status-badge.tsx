import { memo } from "react";
import { Badge } from "@/components/ui/badge";

const STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  peer_reviewed: { label: "Peer Reviewed", variant: "default" },
  awaiting: { label: "Awaiting Review", variant: "secondary" },
  issues: { label: "Issues Flagged", variant: "outline" },
  errors: { label: "Critical Errors", variant: "destructive" },
};

export const ReviewStatusBadge = memo(function ReviewStatusBadge({ status }: { status: string }) {
  const config = STATUS_MAP[status] || { label: status, variant: "secondary" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
});
