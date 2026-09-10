import { ImageResponse } from "next/og";
import { getResult } from "@/lib/store";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const record = await getResult(id);

  const format = record?.result.detected_format ?? "unknown";
  const cause = record ? truncate(record.result.cause, 140) : "This diagnosis was not found.";
  const isPattern = record?.result.source === "pattern";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 64,
          backgroundColor: "#ffffff",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 32, fontWeight: 700, color: "#0f172a", display: "flex" }}>
            WhyDidThisFail?
          </div>
          {record && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "8px 20px",
                borderRadius: 999,
                fontSize: 24,
                fontWeight: 600,
                color: isPattern ? "#047857" : "#6d28d9",
                backgroundColor: isPattern ? "#ecfdf5" : "#f5f3ff",
                border: `2px solid ${isPattern ? "#a7f3d0" : "#ddd6fe"}`,
              }}
            >
              {isPattern ? "Known issue" : "AI analysis"}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              display: "flex",
              fontSize: 28,
              fontWeight: 600,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            {format} failure
          </div>
          <div style={{ display: "flex", fontSize: 44, fontWeight: 700, color: "#0f172a", lineHeight: 1.25 }}>
            {cause}
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
