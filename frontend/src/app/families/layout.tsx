import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Governance Research Families",
  description: "Browse 11 paper families organized by lock protocol — venue-specific, methodology-locked, and open programs targeting journals like Nature, Science, and AI conferences.",
};

export default function FamiliesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
