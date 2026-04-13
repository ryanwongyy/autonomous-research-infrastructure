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
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis domain={[1200, 1800]} />
            <Tooltip />
            <Bar dataKey="elo" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
});
