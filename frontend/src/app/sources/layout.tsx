import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Source Cards",
  description: "Data source registry — access methods, claim permissions, fragility scores, and tier ratings.",
};

export default function SourcesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
