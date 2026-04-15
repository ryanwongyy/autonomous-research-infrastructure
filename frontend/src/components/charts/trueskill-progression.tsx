"use client";

import { memo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TrueSkillProgressionPoint } from "@/lib/types";

interface TrueSkillProgressionProps {
  data: TrueSkillProgressionPoint[];
}

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export const TrueSkillProgression = memo(function TrueSkillProgression({ data }: TrueSkillProgressionProps) {
  // Group by paper_id
  const paperIds = [...new Set(data.map((d) => d.paper_id))];
  const dates = [...new Set(data.map((d) => d.date))].sort();

  const chartData = dates.map((date) => {
    const point: Record<string, string | number> = { date };
    for (const paperId of paperIds) {
      const match = data.find((d) => d.date === date && d.paper_id === paperId);
      if (match) {
        point[paperId] = match.conservative_rating;
      }
    }
    return point;
  });

  const paperTitles: Record<string, string> = {};
  for (const d of data) {
    paperTitles[d.paper_id] = d.title.slice(0, 30);
  }

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          TrueSkill Progression (Top Papers)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label={`Line chart: TrueSkill progression over ${dates.length} dates for top ${Math.min(paperIds.length, 5)} papers.`}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis />
              <Tooltip />
              <Legend />
              {paperIds.slice(0, 5).map((paperId, i) => (
                <Line
                  key={paperId}
                  type="monotone"
                  dataKey={paperId}
                  name={paperTitles[paperId] || paperId}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <details className="mt-2">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
            View data table
          </summary>
          <div className="mt-1 max-h-48 overflow-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr>
                  <th scope="col" className="text-left py-1 pr-3 font-medium sticky top-0 bg-background">Date</th>
                  {paperIds.slice(0, 5).map((id) => (
                    <th key={id} scope="col" className="text-right py-1 pr-3 font-medium sticky top-0 bg-background truncate max-w-[100px]">
                      {paperTitles[id] || id}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {chartData.map((row) => (
                  <tr key={row.date as string}>
                    <td className="py-0.5 pr-3">{row.date as string}</td>
                    {paperIds.slice(0, 5).map((id) => (
                      <td key={id} className="py-0.5 pr-3 text-right font-mono">
                        {row[id] != null ? Number(row[id]).toFixed(1) : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </CardContent>
    </Card>
  );
});
