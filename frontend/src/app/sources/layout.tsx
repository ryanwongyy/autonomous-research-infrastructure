import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Sources & Provenance",
  description: "Transparent source catalog with tier classification, fragility scores, claim permissions, and access methods for all reference data used in paper generation.",
};

export default function SourcesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
