import type { Metadata } from "next";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { serverFetch } from "@/lib/api";
import type { CategoryInfo } from "@/lib/types";

export const metadata: Metadata = {
  title: "Categories",
  description: "Research categories organized by topic with paper counts and leaderboard rankings.",
};

export default async function CategoriesPage() {
  let categories: CategoryInfo[] = [];
  let apiError = false;

  try {
    categories = await serverFetch<CategoryInfo[]>("/categories");
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold">Categories</h1>
      <p className="mt-1 text-muted-foreground">
        Research programs organized by topic, each with dedicated data pipelines and
        identification strategies.
      </p>

      {apiError && (
        <Card className="mt-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Category data may be unavailable.
          </CardContent>
        </Card>
      )}

      <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {categories.map((cat) => (
          <Link key={cat.slug} href={`/categories/${cat.slug}`}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle className="text-lg">{cat.name}</CardTitle>
                <CardDescription>{cat.domain_id}</CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant="secondary">{cat.paper_count} papers</Badge>
              </CardContent>
            </Card>
          </Link>
        ))}
        {categories.length === 0 && (
          <p className="col-span-full text-center text-muted-foreground py-12">
            No categories configured yet. Add a domain configuration to get started.
          </p>
        )}
      </div>
    </div>
  );
}
