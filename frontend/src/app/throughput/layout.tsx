import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Throughput",
  description: "Pipeline throughput — funnel stages, conversion rates, bottlenecks, and projections.",
};

export default function ThroughputLayout({ children }: { children: React.ReactNode }) {
  return children;
}
