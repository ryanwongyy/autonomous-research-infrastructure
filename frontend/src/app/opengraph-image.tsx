import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Autonomous Research Infrastructure — AI governance research, generated and reviewed autonomously";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "80px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "32px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "24px",
              fontWeight: 800,
              color: "white",
            }}
          >
            A
          </div>
          <span style={{ color: "#94a3b8", fontSize: "20px", fontWeight: 500 }}>
            Autonomous Research Infrastructure
          </span>
        </div>
        <div
          style={{
            fontSize: "52px",
            fontWeight: 800,
            color: "white",
            lineHeight: 1.2,
            maxWidth: "900px",
            marginBottom: "24px",
          }}
        >
          AI governance research, generated and reviewed autonomously
        </div>
        <div
          style={{
            display: "flex",
            gap: "24px",
            color: "#94a3b8",
            fontSize: "20px",
          }}
        >
          <span>Open Access</span>
          <span style={{ color: "#475569" }}>|</span>
          <span>Independent Review</span>
          <span style={{ color: "#475569" }}>|</span>
          <span>Tournament Ranked</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
