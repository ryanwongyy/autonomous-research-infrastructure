import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Paper Families",
  description: "Browse paper families — research programs with venue ladders, lock protocols, and funnel stages.",
};

export default function FamiliesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
