import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Family Detail",
  description: "Paper family detail — venue ladder, funnel stages, and paper inventory.",
};

export default function FamilyDetailLayout({ children }: { children: React.ReactNode }) {
  return children;
}
