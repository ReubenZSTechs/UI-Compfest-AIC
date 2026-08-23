// frontend/src/features/optimization/data/analyticsScenariosData.ts
import type { OptimizationCard } from "@/features/project/types/project.types";

export interface StationStatus {
  id: string;
  name: string;
  status: "IMPROVED" | "OPTIMAL" | "BOTTLENECK" | "AUTOMATED";
  badgeColor: "amber" | "green" | "red" | "blue";
  details?: string;
}

export interface ImpactRecommendation {
  id: string;
  rank: string; // e.g. "01"
  priority: "HIGH" | "MEDIUM" | "LOW";
  text: string;
  impactBadge: string; // e.g. "+18% throughput"
}

export interface FlowNode {
  id: string;
  label: string;
  type: "machine" | "conveyor" | "sorter" | "qa";
  status: "improved" | "optimal" | "bottleneck" | "automated";
  assignedWorkers: string[];
}

export interface FlowEdge {
  from: string;
  to: string;
  type: "FLOW";
}

export interface ScenarioData {
  id: string; // "rec_1" | "rec_2" | "rec_3"
  tabNumber: number;
  title: string;
  shortTitle: string;
  subtitle: string;
  constraints: {
    hiring: boolean;
    fireMut: boolean;
    automation: boolean;
    budgetLabel: string;
  };
  metrics: {
    throughput: {
      diff: string; // "+25.0%"
      diffType: "positive" | "negative";
      before: string; // "840/jam"
      after: string; // "1.050/jam"
    };
    errorRate: {
      diff: string; // "-34.1%"
      diffType: "positive" | "negative";
      before: string; // "8.2%"
      after: string; // "5.4%"
    };
    opCost: {
      diff: string; // "-7.1%"
      diffType: "positive" | "negative";
      before: string; // "Rp 4.2M/hr"
      after: string; // "Rp 3.9M/hr"
    };
  };
  shiftChart: {
    labels: string[]; // ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"]
    before: number[]; // [840, 820, 780, 800, 830, 850]
    after: number[]; // [1050, 1040, 1010, 1030, 1060, 1050]
  };
  costChart: {
    categories: string[]; // ["Tenaga Kerja", "Mesin", "Overhead"]
    before: number[]; // [2.2, 1.35, 0.65] (in Juta/Hari)
    after: number[]; // [2.05, 1.35, 0.50]
  };
  stations: StationStatus[];
  graphSubtitle: string;
  flowGraph: {
    nodes: FlowNode[];
    edges: FlowEdge[];
  };
  recommendations: ImpactRecommendation[];
  initialBotMessage: string;
  quickScenarios: string[];
}

function formatBudget(num: number): string {
  if (num >= 1_000_000_000) {
    return `Rp ${(num / 1_000_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  }
  if (num >= 1_000_000) {
    return `Rp ${(num / 1_000_000).toFixed(0)}M`;
  }
  return `Rp ${num.toLocaleString("id-ID")}`;
}

export const ANALYTICS_SCENARIOS: Record<string, ScenarioData> = {
  rec_1: {
    id: "rec_1",
    tabNumber: 1,
    title: "REALOKASI SDM MURNI",
    shortTitle: "1 REALOKASI SDM MURNI",
    subtitle: "Optimasi tanpa rekrut & tanpa otomasi — hanya redistribusi operator yang ada",
    constraints: {
      hiring: false,
      fireMut: false,
      automation: false,
      budgetLabel: "Rp 50M",
    },
    metrics: {
      throughput: {
        diff: "+25.0%",
        diffType: "positive",
        before: "840/jam",
        after: "1.050/jam",
      },
      errorRate: {
        diff: "-34.1%",
        diffType: "positive",
        before: "8.2%",
        after: "5.4%",
      },
      opCost: {
        diff: "-7.1%",
        diffType: "positive",
        before: "Rp 4.2M/hr",
        after: "Rp 3.9M/hr",
      },
    },
    shiftChart: {
      labels: ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"],
      before: [840, 830, 810, 820, 835, 840],
      after: [1050, 1045, 1030, 1040, 1055, 1050],
    },
    costChart: {
      categories: ["Tenaga Kerja", "Mesin", "Overhead"],
      before: [2.2, 1.35, 0.65],
      after: [2.05, 1.35, 0.50],
    },
    stations: [
      {
        id: "mc_a",
        name: "Mesin Cetak A",
        status: "IMPROVED",
        badgeColor: "amber",
        details: "Asisten Ahmad Fauzi (Budi Santoso) ditugaskan",
      },
      {
        id: "cv_1",
        name: "Conveyor Jalur 1",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Laju konveyor stabil tanpa backlog",
      },
      {
        id: "opt_s",
        name: "Optic Sorter",
        status: "BOTTLENECK",
        badgeColor: "red",
        details: "Load 94% — Dewi Ayu dialihkan ke sini",
      },
      {
        id: "cv_2",
        name: "Conveyor Jalur 2",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Flow lancar ke stasiun berikutnya",
      },
      {
        id: "mc_b",
        name: "Mesin Cetak B",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Sinkronisasi produksi stabil",
      },
      {
        id: "sort_p",
        name: "Sortir Pro",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Target per jam konsisten terpenuhi",
      },
    ],
    graphSubtitle: "Skenario 1: Realokasi SDM Murni — 2 perubahan dari baseline",
    flowGraph: {
      nodes: [
        {
          id: "n1",
          label: "Mesin Cetak A",
          type: "machine",
          status: "improved",
          assignedWorkers: ["Ahmad Fauzi", "Budi Santoso (Baru)"],
        },
        {
          id: "n2",
          label: "Conveyor Jalur 1",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Sensor Auto"],
        },
        {
          id: "n3",
          label: "Optic Sorter",
          type: "sorter",
          status: "bottleneck",
          assignedWorkers: ["Dewi Ayu (Keahlian Seleksi 95)"],
        },
        {
          id: "n4",
          label: "Conveyor Jalur 2",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Sensor Auto"],
        },
        {
          id: "n5",
          label: "Mesin Cetak B",
          type: "machine",
          status: "optimal",
          assignedWorkers: ["Rian Pratama"],
        },
        {
          id: "n6",
          label: "Sortir Pro",
          type: "qa",
          status: "optimal",
          assignedWorkers: ["Siti Nurhaliza"],
        },
      ],
      edges: [
        { from: "n1", to: "n2", type: "FLOW" },
        { from: "n2", to: "n3", type: "FLOW" },
        { from: "n3", to: "n4", type: "FLOW" },
        { from: "n4", to: "n5", type: "FLOW" },
        { from: "n5", to: "n6", type: "FLOW" },
      ],
    },
    recommendations: [
      {
        id: "r1",
        rank: "01",
        priority: "HIGH",
        text: "Pindahkan Dewi Ayu ke pos Optic Sorter — skill Seleksi Kontrol 95 adalah yang tertinggi di tim dan cocok untuk titik inspeksi kritis.",
        impactBadge: "+18% throughput",
      },
      {
        id: "r2",
        rank: "02",
        priority: "HIGH",
        text: "Relokasi Budi Santoso dari Conveyor Jalur 1 ke Mesin Cetak A sebagai asisten Ahmad Fauzi — antrean di lini cetak teratasi.",
        impactBadge: "+12% efisiensi",
      },
    ],
    initialBotMessage:
      "Skenario 1 selesai. Throughput naik +25% hanya dengan realokasi SDM — tanpa biaya rekrut atau investasi mesin baru. Siap menerima skenario what-if.",
    quickScenarios: [
      "Bagaimana jika budget dipotong 30%?",
      "Simulasikan tanpa otomatisasi mesin",
      "Jika 2 operator di-PHK?",
    ],
  },

  rec_2: {
    id: "rec_2",
    tabNumber: 2,
    title: "SUBSTITUSI OTOMASI",
    shortTitle: "2 SUBSTITUSI OTOMASI",
    subtitle: "Mesin otomatis mengambil alih pos manual — tanpa rekrut baru, PHK dilarang",
    constraints: {
      hiring: false,
      fireMut: false,
      automation: true,
      budgetLabel: "Rp 50M",
    },
    metrics: {
      throughput: {
        diff: "+42.8%",
        diffType: "positive",
        before: "840/jam",
        after: "1.200/jam",
      },
      errorRate: {
        diff: "-68.3%",
        diffType: "positive",
        before: "8.2%",
        after: "2.6%",
      },
      opCost: {
        diff: "+14.3%",
        diffType: "negative",
        before: "Rp 4.2M/hr",
        after: "Rp 4.8M/hr",
      },
    },
    shiftChart: {
      labels: ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"],
      before: [840, 830, 810, 820, 835, 840],
      after: [1190, 1205, 1195, 1210, 1215, 1200],
    },
    costChart: {
      categories: ["Tenaga Kerja", "Mesin", "Overhead"],
      before: [2.2, 1.35, 0.65],
      after: [1.6, 2.45, 0.75],
    },
    stations: [
      {
        id: "mc_a",
        name: "Mesin Cetak A",
        status: "OPTIMAL",
        badgeColor: "green",
      },
      {
        id: "cv_1",
        name: "Conveyor Jalur 1",
        status: "OPTIMAL",
        badgeColor: "green",
      },
      {
        id: "opt_s",
        name: "Optic Sorter",
        status: "AUTOMATED",
        badgeColor: "green",
        details: "Modul Robotic Feeder terpasang",
      },
      {
        id: "cv_2",
        name: "Conveyor Jalur 2",
        status: "OPTIMAL",
        badgeColor: "green",
      },
      {
        id: "mc_b",
        name: "Mesin Cetak B",
        status: "OPTIMAL",
        badgeColor: "green",
      },
      {
        id: "sort_p",
        name: "Sortir Pro",
        status: "IMPROVED",
        badgeColor: "amber",
        details: "Quality gate didukung sensor optik",
      },
    ],
    graphSubtitle: "Skenario 2: Substitusi Otomasi — 1 mesin baru, 2 operator dipindah",
    flowGraph: {
      nodes: [
        {
          id: "n1",
          label: "Mesin Cetak A",
          type: "machine",
          status: "optimal",
          assignedWorkers: ["Ahmad Fauzi"],
        },
        {
          id: "n2",
          label: "Conveyor Jalur 1",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Sensor Auto"],
        },
        {
          id: "n3",
          label: "Optic Sorter",
          type: "sorter",
          status: "automated",
          assignedWorkers: ["Modul Robotik AI"],
        },
        {
          id: "n4",
          label: "Conveyor Jalur 2",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Sensor Auto"],
        },
        {
          id: "n5",
          label: "Mesin Cetak B",
          type: "machine",
          status: "optimal",
          assignedWorkers: ["Rian Pratama"],
        },
        {
          id: "n6",
          label: "Sortir Pro",
          type: "qa",
          status: "improved",
          assignedWorkers: ["Dewi Ayu", "Siti Nurhaliza"],
        },
      ],
      edges: [
        { from: "n1", to: "n2", type: "FLOW" },
        { from: "n2", to: "n3", type: "FLOW" },
        { from: "n3", to: "n4", type: "FLOW" },
        { from: "n4", to: "n5", type: "FLOW" },
        { from: "n5", to: "n6", type: "FLOW" },
      ],
    },
    recommendations: [
      {
        id: "r1",
        rank: "01",
        priority: "HIGH",
        text: "Pasang modul Robotic Feeder pada pos Optic Sorter untuk menggantikan input manual berkecepatan tinggi.",
        impactBadge: "+28% throughput",
      },
      {
        id: "r2",
        rank: "02",
        priority: "MEDIUM",
        text: "Alihkan operator manual ke stasiun inspeksi akhir (Sortir Pro) untuk quality assurance sekunder.",
        impactBadge: "+15% QA accuracy",
      },
    ],
    initialBotMessage:
      "Skenario 2 siap. Throughput meningkat +42.8% dengan substitusi mesin pada 2 bottleneck utama, hemat beban kerja operator.",
    quickScenarios: [
      "Bagaimana jika conveyor dipercepat 20%?",
      "Hitung payback period mesin baru",
      "Apakah ada risiko downtime mesin?",
    ],
  },

  rec_3: {
    id: "rec_3",
    tabNumber: 3,
    title: "FULL OPTIMIZATION",
    shortTitle: "3 FULL OPTIMIZATION",
    subtitle: "Rekrut + PHK + otomasi semua aktif — solusi terbaik tanpa batasan SDM",
    constraints: {
      hiring: true,
      fireMut: true,
      automation: true,
      budgetLabel: "Rp 120M",
    },
    metrics: {
      throughput: {
        diff: "+78.6%",
        diffType: "positive",
        before: "840/jam",
        after: "1.500/jam",
      },
      errorRate: {
        diff: "-89.0%",
        diffType: "positive",
        before: "8.2%",
        after: "0.9%",
      },
      opCost: {
        diff: "+45.2%",
        diffType: "negative",
        before: "Rp 4.2M/hr",
        after: "Rp 6.1M/hr",
      },
    },
    shiftChart: {
      labels: ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"],
      before: [840, 830, 810, 820, 835, 840],
      after: [1490, 1510, 1500, 1520, 1505, 1500],
    },
    costChart: {
      categories: ["Tenaga Kerja", "Mesin", "Overhead"],
      before: [2.2, 1.35, 0.65],
      after: [2.8, 2.5, 0.8],
    },
    stations: [
      {
        id: "mc_a",
        name: "Mesin Cetak A (Dual Line)",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Duplikasi cetak 2x kapasitas dengan Lead Tech Ahmad Fauzi",
      },
      {
        id: "cv_1",
        name: "Conveyor Jalur 1 (High-speed)",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Sinkronisasi motor servo kecepatan 1.500 unit/jam",
      },
      {
        id: "opt_s",
        name: "Optic Sorter (AI-Core)",
        status: "AUTOMATED",
        badgeColor: "blue",
        details: "Dual AI-Vision System klasifikasi sortir tanpa henti",
      },
      {
        id: "cv_2",
        name: "Conveyor Jalur 2 (High-speed)",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Aliran paralel ganda tanpa titik bottleneck",
      },
      {
        id: "mc_b",
        name: "Mesin Cetak B (Dual Line)",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Lini paralel aktif dengan operator Lead Tech 2",
      },
      {
        id: "sort_p",
        name: "Sortir Pro (AI Vision)",
        status: "OPTIMAL",
        badgeColor: "green",
        details: "Supervisi QA oleh Dewi Ayu dengan akurasi 99.8%",
      },
    ],
    graphSubtitle: "Skenario 3: Full Optimization — Lini ganda paralel & ekspansi penuh",
    flowGraph: {
      nodes: [
        {
          id: "n1",
          label: "Mesin Cetak A (Dual)",
          type: "machine",
          status: "optimal",
          assignedWorkers: ["Lead Tech", "Ahmad Fauzi"],
        },
        {
          id: "n2",
          label: "Conveyor Jalur 1 (High-speed)",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Auto Sync"],
        },
        {
          id: "n3",
          label: "Optic Sorter (AI-Core)",
          type: "sorter",
          status: "automated",
          assignedWorkers: ["Dual Vision System"],
        },
        {
          id: "n4",
          label: "Conveyor Jalur 2 (High-speed)",
          type: "conveyor",
          status: "optimal",
          assignedWorkers: ["Auto Sync"],
        },
        {
          id: "n5",
          label: "Mesin Cetak B (Dual)",
          type: "machine",
          status: "optimal",
          assignedWorkers: ["Lead Tech 2", "Rian Pratama"],
        },
        {
          id: "n6",
          label: "Sortir Pro (AI Vision)",
          type: "qa",
          status: "optimal",
          assignedWorkers: ["Dewi Ayu (Supervisor QA)"],
        },
      ],
      edges: [
        { from: "n1", to: "n2", type: "FLOW" },
        { from: "n2", to: "n3", type: "FLOW" },
        { from: "n3", to: "n4", type: "FLOW" },
        { from: "n4", to: "n5", type: "FLOW" },
        { from: "n5", to: "n6", type: "FLOW" },
      ],
    },
    recommendations: [
      {
        id: "r1",
        rank: "01",
        priority: "HIGH",
        text: "Rekrut 2 Lead Technician & pasang dual-conveyor otomatisasi paralel untuk menduplikasi kapasitas pabrik hingga 1.500 unit/jam.",
        impactBadge: "+45% scale",
      },
      {
        id: "r2",
        rank: "02",
        priority: "HIGH",
        text: "Optimasi siklus shift 3-rotasi dengan insentif lembur terstruktur untuk eliminasi fatigue total operator.",
        impactBadge: "+33% uptime",
      },
    ],
    initialBotMessage:
      "Skenario 3 (Full Optimization) selesai dihitung. Output maksimal 1.500 unit/jam tercapai dengan investasi modal penuh Rp 120M.",
    quickScenarios: [
      "Bagaimana jika demand turun 20% di kuartal 4?",
      "Cek utilitas mesin cetak ganda",
      "Berapa lama payback period ekspansi penuh?",
    ],
  },
};

/**
 * Resolves available scenarios combining generated project draft cards and presets.
 * This guarantees the tab titles, descriptions, and budget badges dynamically follow
 * whatever scenarios are available in the project session.
 */
export function getResolvedScenarios(generatedCards?: OptimizationCard[]): ScenarioData[] {
  const defaultList = [
    ANALYTICS_SCENARIOS.rec_1,
    ANALYTICS_SCENARIOS.rec_2,
    ANALYTICS_SCENARIOS.rec_3,
  ];

  if (!generatedCards || generatedCards.length === 0) {
    return defaultList;
  }

  return defaultList.map((sc, idx) => {
    const card =
      generatedCards.find(
        (c) =>
          c.id?.toLowerCase() === sc.id.toLowerCase() ||
          c.id?.toLowerCase() === `rec_${idx + 1}` ||
          c.id?.toLowerCase() === `rec_${sc.tabNumber}` ||
          c.id?.toLowerCase() === `card_${idx + 1}`
      ) || generatedCards[idx];

    if (!card) return sc;

    return {
      ...sc,
      id: card.id || sc.id,
      title: card.title ? card.title.toUpperCase() : sc.title,
      shortTitle: `${sc.tabNumber} ${(card.title || sc.title).toUpperCase()}`,
      subtitle: card.description || sc.subtitle,
      constraints: {
        ...sc.constraints,
        budgetLabel: card.budget ? formatBudget(card.budget) : sc.constraints.budgetLabel,
      },
    };
  });
}
