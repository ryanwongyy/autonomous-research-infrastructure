import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RatingDistribution } from "../rating-distribution";
import { EloBySource } from "../elo-by-source";
import type { RatingDistributionBucket } from "@/lib/types";

// Mock recharts — SVG charts don't render in jsdom, so we mock to test data flow
vi.mock("recharts", () => {
  const FakeResponsiveContainer = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  );
  const FakeBarChart = ({ children, data }: { children: React.ReactNode; data: unknown[] }) => (
    <div data-testid="bar-chart" data-count={data.length}>{children}</div>
  );
  return {
    ResponsiveContainer: FakeResponsiveContainer,
    BarChart: FakeBarChart,
    LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Bar: () => null,
    Line: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

describe("RatingDistribution", () => {
  const sampleData: RatingDistributionBucket[] = [
    { bucket_start: 10, bucket_end: 15, count_ai: 3, count_benchmark: 5 },
    { bucket_start: 15, bucket_end: 20, count_ai: 7, count_benchmark: 2 },
    { bucket_start: 20, bucket_end: 25, count_ai: 4, count_benchmark: 4 },
  ];

  it("renders the title", () => {
    render(<RatingDistribution data={sampleData} title="Conservative Rating Distribution" />);
    expect(screen.getByText("Conservative Rating Distribution")).toBeInTheDocument();
  });

  it("has an accessible aria-label on the chart container", () => {
    render(<RatingDistribution data={sampleData} title="Rating Distribution" />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("Rating Distribution");
    expect(chart.getAttribute("aria-label")).toContain("3 rating buckets");
  });

  it("renders the data table fallback", () => {
    render(<RatingDistribution data={sampleData} title="Rating Distribution" />);
    // The details/summary element provides a data table fallback
    expect(screen.getByText("View data table")).toBeInTheDocument();
  });

  it("renders correct table headers", () => {
    render(<RatingDistribution data={sampleData} title="Test" />);
    expect(screen.getByText("Rating")).toBeInTheDocument();
    expect(screen.getByText("AI Papers")).toBeInTheDocument();
    expect(screen.getByText("Benchmark")).toBeInTheDocument();
  });

  it("renders table rows with formatted bucket starts", () => {
    render(<RatingDistribution data={sampleData} title="Test" />);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("renders counts in the data table", () => {
    render(<RatingDistribution data={sampleData} title="Test" />);
    // Check AI paper counts appear
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("handles empty data array", () => {
    render(<RatingDistribution data={[]} title="Empty Chart" />);
    expect(screen.getByText("Empty Chart")).toBeInTheDocument();
    expect(screen.getByText("View data table")).toBeInTheDocument();
  });
});

describe("EloBySource", () => {
  it("renders the title", () => {
    render(<EloBySource avgEloAi={1450} avgEloBenchmark={1520} />);
    expect(screen.getByText("Average Elo by Source")).toBeInTheDocument();
  });

  it("has an accessible aria-label with values", () => {
    render(<EloBySource avgEloAi={1450} avgEloBenchmark={1520} />);
    const chart = screen.getByRole("img");
    const label = chart.getAttribute("aria-label")!;
    expect(label).toContain("1450");
    expect(label).toContain("1520");
  });

  it("handles null AI elo gracefully", () => {
    render(<EloBySource avgEloAi={null} avgEloBenchmark={1500} />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("N/A");
  });

  it("handles null benchmark elo gracefully", () => {
    render(<EloBySource avgEloAi={1400} avgEloBenchmark={null} />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("N/A");
  });

  it("renders the data table with formatted values", () => {
    render(<EloBySource avgEloAi={1450.7} avgEloBenchmark={1520.3} />);
    expect(screen.getByText("View data table")).toBeInTheDocument();
    // Table shows integer-formatted values
    expect(screen.getByText("1451")).toBeInTheDocument();
    expect(screen.getByText("1520")).toBeInTheDocument();
  });

  it("renders table headers", () => {
    render(<EloBySource avgEloAi={1400} avgEloBenchmark={1500} />);
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByText("Avg Elo")).toBeInTheDocument();
  });

  it("uses 0 for null values in the data table", () => {
    render(<EloBySource avgEloAi={null} avgEloBenchmark={null} />);
    // Both should show "0" in the table
    const zeroCells = screen.getAllByText("0");
    expect(zeroCells.length).toBe(2);
  });
});
