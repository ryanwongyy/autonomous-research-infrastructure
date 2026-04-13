import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Leaderboard",
  description: "Paper rankings by family — TrueSkill and Elo ratings from the tournament system.",
};

export default function LeaderboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
