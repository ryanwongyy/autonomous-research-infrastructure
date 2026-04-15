"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { FamilyCard } from "@/components/family/family-card";
import { getFamilies } from "@/lib/api";
import type { PaperFamily } from "@/lib/types";

export default function FamiliesPage() {
  const [families, setFamilies] = useState<PaperFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await getFamilies();
        setFamilies(res.families);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const { venueLocked, methodLocked, openFamilies } = useMemo(() => ({
    venueLocked: families.filter((f) => f.lock_protocol_type === "venue-lock"),
    methodLocked: families.filter((f) => f.lock_protocol_type === "method-lock"),
    openFamilies: families.filter((f) => f.lock_protocol_type === "open"),
  }), [families]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Paper Families</h1>
        <p className="mt-2 text-muted-foreground max-w-2xl">
          Research is organized into 11 families, each focused on a different aspect
          of AI governance. Some target specific top-tier journals (venue-locked),
          others use fixed methodologies (method-locked), and some explore freely
          across topics and venues (open).
        </p>
      </div>

      {error && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Family data may be unavailable.
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="h-44 animate-pulse bg-muted/50" />
          ))}
        </div>
      ) : families.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            No paper families available. Ensure the backend API is running.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-10">
          {/* Venue-locked families */}
          {venueLocked.length > 0 && (
            <div>
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-xl font-semibold">Venue-Locked</h2>
                <span className="inline-flex items-center rounded-md bg-purple-100 dark:bg-purple-900/40 px-2 py-0.5 text-xs font-medium text-purple-700 dark:text-purple-300">
                  {venueLocked.length} families
                </span>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                Papers target a specific flagship journal. Design, methods, and framing are
                constrained by the target venue requirements.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {venueLocked.map((f) => (
                  <FamilyCard key={f.id} family={f} />
                ))}
              </div>
            </div>
          )}

          {/* Method-locked families */}
          {methodLocked.length > 0 && (
            <div>
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-xl font-semibold">Method-Locked</h2>
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300">
                  {methodLocked.length} families
                </span>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                Papers use a fixed methodological approach. The method is locked but the
                target venue may vary by paper topic.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {methodLocked.map((f) => (
                  <FamilyCard key={f.id} family={f} />
                ))}
              </div>
            </div>
          )}

          {/* Open families */}
          {openFamilies.length > 0 && (
            <div>
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-xl font-semibold">Open</h2>
                <span className="inline-flex items-center rounded-md bg-green-100 dark:bg-green-900/40 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-300">
                  {openFamilies.length} families
                </span>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                Papers have flexible venue targeting and method selection. Suitable for
                exploratory or cross-cutting research themes.
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {openFamilies.map((f) => (
                  <FamilyCard key={f.id} family={f} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
