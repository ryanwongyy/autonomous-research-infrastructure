"use client";

import { useEffect, useMemo, useState } from "react";
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
      aria-label={`${source.name} source card, click to ${expanded ? "collapse" : "expand"} details`}
      className={`cursor-pointer transition-all hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:outline-none ${
        expanded ? "shadow-md border-primary/30 ring-1 ring-primary/10" : ""
      }`}
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
          <div className="flex items-center gap-2">
            <span
              className={`text-muted-foreground transition-transform text-xs ${expanded ? "rotate-90" : ""}`}
              aria-hidden="true"
            >
              &#x25B8;
            </span>
            <CardTitle className="text-sm leading-snug">{source.name}</CardTitle>
          </div>
          <SourceTierBadge tier={source.tier} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{source.access_method}</span>
          {source.requires_key && (
            <Badge variant="outline" className="text-[11px] px-1.5 py-0">
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
          <p className="mt-1 text-xs text-muted-foreground inline-flex items-center gap-1">
            <span>Fragility: </span>
            <span className={`font-mono font-semibold ${
              source.fragility_score >= 3
                ? "text-red-600 dark:text-red-400"
                : source.fragility_score >= 1.5
                ? "text-amber-600 dark:text-amber-400"
                : "text-emerald-600 dark:text-emerald-400"
            }`}>
              {source.fragility_score.toFixed(1)}
            </span>
            <span className="relative group/frag">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="opacity-50 hover:opacity-100 cursor-help"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
              <span className="invisible group-hover/frag:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 w-48 rounded-md bg-popover border border-border p-2 text-[11px] text-popover-foreground shadow-md z-20">
                How likely this source is to break or return unreliable data. Lower is better. Above 3.0 = high risk.
              </span>
            </span>
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
                    <Badge key={p} variant="secondary" className="text-[11px]">
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
                    <Badge key={p} variant="destructive" className="text-[11px]">
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

  const tierA = useMemo(() => sources.filter((s) => s.tier === "A"), [sources]);
  const tierB = useMemo(() => sources.filter((s) => s.tier === "B"), [sources]);
  const tierC = useMemo(() => sources.filter((s) => s.tier === "C"), [sources]);

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
