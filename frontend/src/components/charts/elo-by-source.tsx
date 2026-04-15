"use client";

import { memo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface EloBySourceProps {
  avgEloAi: number | null;
  avgEloBenchmark: number | null;
}

export const EloBySource = memo(function EloBySource({ avgEloAi, avgEloBenchmark }: EloBySourceProps) {
  const data = [
    { name: "AI Papers", elo: avgEloAi ?? 0 },
    { name: "Benchmark", elo: avgEloBenchmark ?? 0 },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Average Elo by Source</CardTitle>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label={`Bar chart: Average Elo by Source. AI Papers: ${avgEloAi?.toFixed(0) ?? "N/A"}, Benchmark: ${avgEloBenchmark?.toFixed(0) ?? "N/A"}.`}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[1200, 1800]} />
              <Tooltip />
              <Bar dataKey="elo" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <details className="mt-2">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
            View data table
          </summary>
          <table className="mt-1 w-full text-xs border-collapse">
            <thead>
              <tr>
                <th scope="col" className="text-left py-1 pr-4 font-medium">Source</th>
                <th scope="col" className="text-right py-1 font-medium">Avg Elo</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.name}>
                  <td className="py-0.5 pr-4">{row.name}</td>
                  <td className="py-0.5 text-right font-mono">{row.elo.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </CardContent>
    </Card>
  );
});
