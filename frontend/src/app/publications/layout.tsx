import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Governance Publications",
  description:
    "Browse AI governance research papers that have passed all review layers. Filter by topic, method, and date. Free, open access with full review history.",
};

export default function PublicationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
