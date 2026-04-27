import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Paper Rankings — TrueSkill Tournament Leaderboard",
  description: "AI governance papers ranked by conservative TrueSkill rating. Compare generated papers against peer-reviewed benchmarks in competitive tournament evaluation.",
};

export default function LeaderboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
