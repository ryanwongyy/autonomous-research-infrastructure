import Link from "next/link";
import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { LeaderboardTable } from "@/components/leaderboard/leaderboard-table";
import { serverFetch } from "@/lib/api";
import type { LeaderboardEntry } from "@/lib/types";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const name = slug.replace(/_/g, " ");
  return {
    title: name,
    description: `Leaderboard and papers for the ${name} research category.`,
  };
}

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  let data: { slug: string; entries: LeaderboardEntry[]; total: number } | null = null;
  let apiError = false;

  try {
    data = await serverFetch<{ slug: string; entries: LeaderboardEntry[]; total: number }>(`/categories/${slug}`);
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted-foreground">
        <Link href="/categories" className="hover:text-foreground">
          Categories
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground capitalize">{slug.replace(/_/g, " ")}</span>
      </nav>

      <h1 className="text-3xl font-bold capitalize">
        {slug.replace(/_/g, " ")}
      </h1>
      <p className="mt-1 text-muted-foreground">
        {data ? `${data.total} papers in this category` : apiError ? "Unable to load data." : "No data available."}
      </p>

      {apiError && (
        <Card className="mt-4 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Category data may be unavailable.
          </CardContent>
        </Card>
      )}

      <div className="mt-6">
        <LeaderboardTable entries={data?.entries ?? []} />
      </div>
    </div>
  );
}
