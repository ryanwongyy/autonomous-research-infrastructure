import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pipeline Throughput & Conversion Metrics",
  description: "Real-time funnel visualization, stage-by-stage conversion rates, bottleneck analysis, and annual projections across all paper families.",
};

export default function ThroughputLayout({ children }: { children: React.ReactNode }) {
  return children;
}
