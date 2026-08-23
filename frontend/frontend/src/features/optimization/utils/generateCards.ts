// frontend/src/features/optimization/utils/generateCards.ts
// Generator (mock AI) untuk 3 kartu rekomendasi optimasi berbasis isi draft:
// graph canvas + operational settings. Budget setiap skenario di-cap oleh
// budgetLimit bila diatur; bila tidak, dipakai baseline 50 juta IDR.
import type {
  OptimizationCard,
  ProjectDraft,
} from "@/features/project/types/project.types";

const DEFAULT_BUDGET = 50_000_000;

function roundToThousands(value: number): number {
  return Math.round(value / 1000) * 1000;
}

export async function generateOptimizationCards(
  draft: ProjectDraft
): Promise<OptimizationCard[]> {
  // Simulasi waktu kalkulasi AI.
  await new Promise((resolve) => setTimeout(resolve, 1200));

  const { nodes, edges } = draft.canvasData;
  const processes = nodes.filter((n) => n.data.kind === "process").length;
  const workers = nodes.filter((n) => n.data.kind === "worker").length;
  const outputs = nodes.filter((n) => n.data.kind === "output");
  const targetOutput =
    outputs.length > 0
      ? (outputs[0].data as Extract<typeof outputs[0]["data"], { kind: "output" }>).targetOutput
      : 0;
  const flowCount = edges.filter((e) => e.data?.relation === "FLOW").length;
  const assignedCount = edges.filter((e) => e.data?.relation === "ASSIGNED_TO").length;

  const maxBudget = draft.agentData.operationalSettings.budgetLimit || DEFAULT_BUDGET;
  const cap = (fraction: number) =>
    roundToThousands(Math.min(maxBudget, maxBudget * fraction));

  const context =
    processes === 0
      ? "Kanvas masih kosong — skenario dibuat dengan asumsi baseline pabrik."
      : `${processes} proses, ${workers} pekerja, ${flowCount} koneksi FLOW, ${assignedCount} penugasan.`;

  const cards: OptimizationCard[] = [
    {
      id: "rec_1",
      title: "Skenario A — Optimasi Penjadwalan",
      budget: cap(0.4),
      description:
        `Rotasi & penjadwalan ulang ${workers} pekerja pada ${processes} proses untuk menekan fatigue tanpa investasi besar. ` +
        `Cocok bila target ${targetOutput || "output"} unit dapat dicapai dengan alur saat ini. ${context}`,
    },
    {
      id: "rec_2",
      title: "Skenario B — Paralelisme Lini",
      budget: cap(0.7),
      description:
        `Buka jalur paralel pada ${processes} proses kritis dan tambah ${Math.max(1, Math.ceil(workers / 2))} pekerja terlatih ` +
        `untuk memecah bottleneck FLOW (${flowCount} koneksi). Trade-off: biaya operasional naik, throughput naik signifikan.`,
    },
    {
      id: "rec_3",
      title: "Skenario C — Ekspansi Kapasitas Penuh",
      budget: cap(0.95),
      description:
        `Ekspansi penuh: tambahan stasiun kerja + staf baru + jam lembur untuk mengejar target ${targetOutput || "output"} unit ` +
        `secepat mungkin. Risiko tertinggi dari segi biaya, paling agresif terhadap bottleneck saat ini.`,
    },
  ];

  return cards;
}
