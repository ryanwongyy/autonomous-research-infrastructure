"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SourceTierBadge } from "@/components/sources/source-tier-badge";
import { getSources } from "@/lib/api";
import type { SourceCard } from "@/lib/types";

function SourceCardItem({ source }: { source: SourceCard }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      className="cursor-pointer transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:outline-none"
      onClick={() => setExpanded(!expanded)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm leading-snug">{source.name}</CardTitle>
          <SourceTierBadge tier={source.tier} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{source.access_method}</span>
          {source.requires_key && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
              Key Required
            </Badge>
          )}
        </div>
        {source.canonical_unit && (
          <p className="mt-1 text-xs text-muted-foreground">
            Unit: {source.canonical_unit}
          </p>
        )}
        {source.fragility_score > 0 && (
          <p className="mt-1 text-xs text-muted-foreground">
            Fragility: {source.fragility_score.toFixed(1)}
          </p>
        )}

        {expanded && (
          <div className="mt-4 space-y-3 border-t pt-3">
            {/* Claim Permissions */}
            {source.claim_permissions.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-1">Claim Permissions</p>
                <div className="flex flex-wrap gap-1">
                  {source.claim_permissions.map((p) => (
                    <Badge key={p} variant="secondary" className="text-[10px]">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Prohibitions */}
            {source.claim_prohibitions.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-1 text-red-600 dark:text-red-400">Prohibitions</p>
                <div className="flex flex-wrap gap-1">
                  {source.claim_prohibitions.map((p) => (
                    <Badge key={p} variant="destructive" className="text-[10px]">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Known Traps */}
            {source.known_traps.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-1 text-amber-600 dark:text-amber-400">Known Traps</p>
                <ul className="space-y-1">
                  {source.known_traps.map((t, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500 dark:bg-amber-400" />
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block text-xs text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Visit source
              </a>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await getSources();
        setSources(res.sources);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const tierA = sources.filter((s) => s.tier === "A");
  const tierB = sources.filter((s) => s.tier === "B");
  const tierC = sources.filter((s) => s.tier === "C");

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Source Registry</h1>
        <p className="mt-2 text-muted-foreground max-w-2xl">
          Registered data sources with claim-permission profiles. Each source card
          specifies what claims can be made, what is prohibited, and known analytical traps.
          Click any card to expand details.
        </p>
      </div>

      {error && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Source data may be unavailable.
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="h-32 animate-pulse bg-muted/50" />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            No sources available. Ensure the backend API is running.
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="all">
          <TabsList>
            <TabsTrigger value="all">
              All ({sources.length})
            </TabsTrigger>
            <TabsTrigger value="A">
              Tier A ({tierA.length})
            </TabsTrigger>
            <TabsTrigger value="B">
              Tier B ({tierB.length})
            </TabsTrigger>
            <TabsTrigger value="C">
              Tier C ({tierC.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all" className="mt-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sources.map((s) => (
                <SourceCardItem key={s.id} source={s} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="A" className="mt-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tierA.map((s) => (
                <SourceCardItem key={s.id} source={s} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="B" className="mt-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tierB.map((s) => (
                <SourceCardItem key={s.id} source={s} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="C" className="mt-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {tierC.map((s) => (
                <SourceCardItem key={s.id} source={s} />
              ))}
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
