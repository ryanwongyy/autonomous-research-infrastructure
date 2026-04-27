import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://ari.example.com";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date().toISOString();

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    { url: `${BASE_URL}/`, lastModified: now, changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE_URL}/publications`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${BASE_URL}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${BASE_URL}/methodology`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${BASE_URL}/families`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE_URL}/leaderboard`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/outcomes`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE_URL}/corrections`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE_URL}/reliability`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE_URL}/failures`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${BASE_URL}/sources`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${BASE_URL}/categories`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${BASE_URL}/rsi`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${BASE_URL}/throughput`, lastModified: now, changeFrequency: "daily", priority: 0.5 },
  ];

  // Dynamic pages: papers and families (fetched at build time, graceful on failure)
  let paperPages: MetadataRoute.Sitemap = [];
  let familyPages: MetadataRoute.Sitemap = [];

  try {
    const res = await fetch(`${API_BASE}/papers/public?limit=500`, { cache: "no-store" });
    if (res.ok) {
      const papers: Array<{ id: string; created_at?: string }> = await res.json();
      paperPages = papers.map((p) => ({
        url: `${BASE_URL}/papers/${p.id}`,
        lastModified: p.created_at ?? now,
        changeFrequency: "weekly" as const,
        priority: 0.8,
      }));
    }
  } catch { /* API unavailable — skip dynamic papers */ }

  try {
    const res = await fetch(`${API_BASE}/families`, { cache: "no-store" });
    if (res.ok) {
      const data: { families: Array<{ id: string }> } = await res.json();
      familyPages = data.families.map((f) => ({
        url: `${BASE_URL}/families/${f.id}`,
        lastModified: now,
        changeFrequency: "weekly" as const,
        priority: 0.7,
      }));
    }
  } catch { /* API unavailable — skip dynamic families */ }

  return [...staticPages, ...paperPages, ...familyPages];
}
