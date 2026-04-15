"use client";

import { memo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RatingDistributionBucket } from "@/lib/types";

interface RatingDistributionProps {
  data: RatingDistributionBucket[];
  title: string;
}

export const RatingDistribution = memo(function RatingDistribution({ data, title }: RatingDistributionProps) {
  const chartData = data.map((bucket) => ({
    range: `${bucket.bucket_start.toFixed(0)}`,
    "AI Papers": bucket.count_ai,
    Benchmark: bucket.count_benchmark,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label={`Bar chart: ${title}. ${chartData.length} rating buckets comparing AI-generated papers against benchmarks.`}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="range" fontSize={12} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="AI Papers"
                fill="hsl(var(--chart-1))"
                opacity={0.7}
                radius={[2, 2, 0, 0]}
              />
              <Bar
                dataKey="Benchmark"
                fill="hsl(var(--chart-3))"
                opacity={0.7}
                radius={[2, 2, 0, 0]}
              />
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
                <th scope="col" className="text-left py-1 pr-4 font-medium">Rating</th>
                <th scope="col" className="text-right py-1 pr-4 font-medium">AI Papers</th>
                <th scope="col" className="text-right py-1 font-medium">Benchmark</th>
              </tr>
            </thead>
            <tbody>
              {chartData.map((row) => (
                <tr key={row.range}>
                  <td className="py-0.5 pr-4">{row.range}</td>
                  <td className="py-0.5 pr-4 text-right font-mono">{row["AI Papers"]}</td>
                  <td className="py-0.5 text-right font-mono">{row.Benchmark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </CardContent>
    </Card>
  );
});
