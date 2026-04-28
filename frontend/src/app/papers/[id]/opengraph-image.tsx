import { ImageResponse } from "next/og";
import { serverFetch } from "@/lib/api";

export const runtime = "edge";
export const alt = "Paper detail — Autonomous Research Infrastructure";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function PaperOGImage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let title = "Research Paper";
  let category = "";
  let method = "";
  let status = "";

  try {
    const paper = await serverFetch<{
      title: string;
      category?: string | null;
      method?: string | null;
      review_status?: string;
    }>(`/papers/${id}`);
    title = paper.title;
    category = paper.category ?? "";
    method = paper.method ?? "";
    status = paper.review_status ?? "";
  } catch {
    /* use defaults */
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "80px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginBottom: "40px",
            }}
          >
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "20px",
                fontWeight: 800,
                color: "white",
              }}
            >
              A
            </div>
            <span style={{ color: "#94a3b8", fontSize: "18px", fontWeight: 500 }}>
              Autonomous Research Infrastructure
            </span>
          </div>
          <div
            style={{
              fontSize: "44px",
              fontWeight: 800,
              color: "white",
              lineHeight: 1.25,
              maxWidth: "950px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
            }}
          >
            {title}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            gap: "16px",
            alignItems: "center",
          }}
        >
          {category && (
            <span
              style={{
                background: "#1e40af",
                color: "#bfdbfe",
                padding: "6px 16px",
                borderRadius: "6px",
                fontSize: "16px",
                fontWeight: 600,
              }}
            >
              {category}
            </span>
          )}
          {method && (
            <span
              style={{
                background: "#374151",
                color: "#d1d5db",
                padding: "6px 16px",
                borderRadius: "6px",
                fontSize: "16px",
                fontWeight: 600,
              }}
            >
              {method}
            </span>
          )}
          {status && (
            <span
              style={{
                background: "#065f46",
                color: "#a7f3d0",
                padding: "6px 16px",
                borderRadius: "6px",
                fontSize: "16px",
                fontWeight: 600,
              }}
            >
              {status}
            </span>
          )}
          <span style={{ color: "#64748b", fontSize: "16px", marginLeft: "auto" }}>
            Open Access
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}
