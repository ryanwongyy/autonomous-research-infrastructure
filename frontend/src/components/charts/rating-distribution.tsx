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
        <ResponsiveContainer width="100%" height={250} aria-label={`Bar chart: ${title}`}>
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
      </CardContent>
    </Card>
  );
});
