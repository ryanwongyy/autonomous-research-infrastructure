"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/api";

interface PublicPaper {
  id: string;
  title: string;
  abstract: string | null;
  family_id: string | null;
  release_status: string;
  funnel_stage: string;
  category: string | null;
  method: string | null;
  novelty_score: number | null;
  overall_screening_score: number | null;
  created_at: string | null;
}

export default function PublicationsPage() {
  const [papers, setPapers] = useState<PublicPaper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/papers/public?limit=100`, {
          signal: AbortSignal.timeout(15_000),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setPapers(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load papers");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statusColor: Record<string, string> = {
    candidate: "bg-amber-100 text-amber-800",
    submitted: "bg-blue-100 text-blue-800",
    public: "bg-green-100 text-green-800",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Publications</h1>
        <p className="text-muted-foreground mt-1">
          Papers that have passed all review layers and reached candidate or
          public status in the autonomous pipeline.
        </p>
      </div>

      {loading && <p className="text-muted-foreground">Loading papers...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}

      {!loading && papers.length === 0 && !error && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No published papers yet. The autonomous pipeline will populate
              this page as papers pass review.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {papers.map((paper) => (
          <Link key={paper.id} href={`/papers/${paper.id}`}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-4">
                  <CardTitle className="text-lg leading-snug">
                    {paper.title}
                  </CardTitle>
                  <Badge
                    variant="secondary"
                    className={
                      statusColor[paper.release_status] ?? "bg-gray-100"
                    }
                  >
                    {paper.release_status}
                  </Badge>
                </div>
                <CardDescription className="flex gap-2 flex-wrap mt-1">
                  {paper.family_id && (
                    <span className="text-xs font-mono">
                      {paper.family_id}
                    </span>
                  )}
                  {paper.method && (
                    <Badge variant="outline" className="text-xs">
                      {paper.method}
                    </Badge>
                  )}
                  {paper.category && (
                    <Badge variant="outline" className="text-xs">
                      {paper.category}
                    </Badge>
                  )}
                  {paper.novelty_score != null && (
                    <span className="text-xs text-muted-foreground">
                      Novelty: {paper.novelty_score.toFixed(1)}
                    </span>
                  )}
                  {paper.created_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(paper.created_at).toLocaleDateString()}
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              {paper.abstract && (
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {paper.abstract}
                  </p>
                </CardContent>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
