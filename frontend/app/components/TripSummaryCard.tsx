"use client";

import { z } from "zod";

// Schema Zod = contrato con el agente. El agente verá este schema como
// los parámetros de la herramienta y CopilotKit los validará antes de
// pasártelos como props.
export const tripSummaryPropsSchema = z.object({
  city: z.string().describe("Ciudad de destino, p. ej. 'Lisboa'"),
  numDays: z.number().int().min(1).describe("Número de días del viaje"),
  totalActivities: z
    .number()
    .int()
    .min(0)
    .describe("Cantidad total de actividades planeadas en todo el viaje"),
  highlight: z
    .string()
    .optional()
    .describe(
      "Una frase corta y atractiva resumiendo el viaje, p. ej. " +
        "'Tres días entre museos y tapas en el corazón de Madrid'"
    ),
});

export type TripSummaryProps = z.infer<typeof tripSummaryPropsSchema>;

export function TripSummaryCard({
  city,
  numDays,
  totalActivities,
  highlight,
}: TripSummaryProps) {
  return (
    <div
      style={{
        border: "1px solid #c7d2fe",
        background: "linear-gradient(135deg,#eef2ff,#fef3c7)",
        borderRadius: 12,
        padding: "16px 18px",
        margin: "8px 0",
        maxWidth: 320,
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>
        ✈️ Itinerary ready
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
        {city}
      </div>
      <div style={{ display: "flex", gap: 16, fontSize: 14 }}>
        <span>
          <strong>{numDays}</strong> día{numDays === 1 ? "" : "s"}
        </span>
        <span>
          <strong>{totalActivities}</strong> actividade
          {totalActivities === 1 ? "" : "s"}
        </span>
      </div>
      {highlight && (
        <p style={{ marginTop: 10, fontSize: 13, color: "#374151" }}>
          {highlight}
        </p>
      )}
    </div>
  );
}
