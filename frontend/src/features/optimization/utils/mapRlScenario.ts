import type {
  FlowEdge,
  FlowNode,
  ImpactRecommendation,
  ScenarioData,
  StationStatus,
} from "../data/analyticsScenariosData";
import type { RlScenario, RlStaffPosition } from "../types/rlScenario.types";

const SHIFT_LABELS = ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"];
const SHIFT_PROFILE = [1.0, 0.985, 0.955, 0.97, 1.005, 1.0];
const COST_CATEGORIES = ["Tenaga Kerja", "Mesin", "Overhead"];
const COST_SPLIT = [0.52, 0.33, 0.15];

export function formatStationLabel(stationId?: string | null): string {
  if (!stationId) return "Standby";

  const stripped = stationId.replace(/^step[_-]?\d*[_-]?/i, "");
  const source = stripped || stationId;

  return source
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRupiahShort(value: number): string {
  if (value >= 1_000_000_000) {
    return `Rp ${(value / 1_000_000_000).toFixed(2)}Mr`;
  }
  if (value >= 1_000_000) {
    return `Rp ${(value / 1_000_000).toFixed(2)}Jt`;
  }
  return `Rp ${Math.round(value).toLocaleString("id-ID")}`;
}

function formatBudgetLabel(value: number): string {
  if (value <= 0) return "Tanpa Capex";
  return formatRupiahShort(value);
}

function formatDelta(deltaPct?: number | null): string {
  if (deltaPct === null || deltaPct === undefined) return "—";
  return `${deltaPct > 0 ? "+" : ""}${deltaPct.toFixed(1)}%`;
}

function diffType(isImprovement?: boolean | null): "positive" | "negative" {
  return isImprovement ? "positive" : "negative";
}

function buildSeries(base: number): number[] {
  return SHIFT_PROFILE.map((factor) => Number((base * factor).toFixed(1)));
}

function buildCostSeries(total: number): number[] {
  return COST_SPLIT.map((share) =>
    Number(((total * share) / 1_000_000).toFixed(2))
  );
}

function stationOrder(positions: RlStaffPosition[]): string[] {
  const seen: string[] = [];

  positions.forEach((position) => {
    const station = position.optimal_station;
    if (station && !seen.includes(station)) {
      seen.push(station);
    }
  });

  return seen;
}

function buildStations(scenario: RlScenario): StationStatus[] {
  const flow = scenario.factory_flow_optimal;
  const automated = new Set(
    flow.asset_upgrades.map((upgrade) => upgrade.workflow_step ?? "")
  );
  const receiving = new Set(
    flow.reallocation_moves.map((move) => move.to_station ?? "")
  );

  return stationOrder(flow.optimal_staff_positions).map((stationId) => {
    const isBottleneck = flow.residual_bottleneck === stationId;
    const isAutomated = automated.has(stationId);
    const isImproved = receiving.has(stationId);

    const status: StationStatus["status"] = isBottleneck
      ? "BOTTLENECK"
      : isAutomated
        ? "AUTOMATED"
        : isImproved
          ? "IMPROVED"
          : "OPTIMAL";

    const badgeColor: StationStatus["badgeColor"] = isBottleneck
      ? "red"
      : isAutomated
        ? "blue"
        : isImproved
          ? "amber"
          : "green";

    const staff = flow.optimal_staff_positions
      .filter((position) => position.optimal_station === stationId)
      .map((position) => position.name)
      .join(", ");

    return {
      id: stationId,
      name: formatStationLabel(stationId),
      status,
      badgeColor,
      details: staff ? `Operator: ${staff}` : "Tanpa operator manual",
    };
  });
}

function buildFlowGraph(scenario: RlScenario): {
  nodes: FlowNode[];
  edges: FlowEdge[];
} {
  const stations = buildStations(scenario);
  const flow = scenario.factory_flow_optimal;

  const nodes: FlowNode[] = stations.map((station) => ({
    id: station.id,
    label: station.name,
    type: station.status === "AUTOMATED" ? "sorter" : "machine",
    status: station.status.toLowerCase() as FlowNode["status"],
    assignedWorkers: flow.optimal_staff_positions
      .filter((position) => position.optimal_station === station.id)
      .map((position) => position.name),
  }));

  const edges: FlowEdge[] = nodes.slice(0, -1).map((node, index) => ({
    from: node.id,
    to: nodes[index + 1].id,
    type: "FLOW",
  }));

  return { nodes, edges };
}

function buildRecommendations(scenario: RlScenario): ImpactRecommendation[] {
  const flow = scenario.factory_flow_optimal;
  const items: ImpactRecommendation[] = [];

  flow.reallocation_moves.forEach((move) => {
    items.push({
      id: move.move_id,
      rank: String(items.length + 1).padStart(2, "0"),
      priority: move.final_fatigue >= 0.65 ? "HIGH" : "MEDIUM",
      text: `Pindahkan ${move.name} (${move.worker_id}) dari ${formatStationLabel(
        move.from_station
      )} ke ${formatStationLabel(move.to_station)}.`,
      impactBadge: `Fatigue ${(move.final_fatigue * 100).toFixed(0)}%`,
    });
  });

  flow.asset_upgrades.forEach((upgrade) => {
    items.push({
      id: `upgrade-${upgrade.asset_id}`,
      rank: String(items.length + 1).padStart(2, "0"),
      priority: "HIGH",
      text: `Otomasi ${formatStationLabel(upgrade.workflow_step)} (${upgrade.asset_id}).`,
      impactBadge: formatRupiahShort(upgrade.capex_rp),
    });
  });

  flow.new_hires.forEach((hire) => {
    items.push({
      id: `hire-${hire.worker_id}`,
      rank: String(items.length + 1).padStart(2, "0"),
      priority: "MEDIUM",
      text: `Rekrut operator baru untuk ${formatStationLabel(hire.assigned_station)}.`,
      impactBadge: formatRupiahShort(hire.capex_rp),
    });
  });

  if (flow.residual_bottleneck) {
    items.push({
      id: "residual",
      rank: String(items.length + 1).padStart(2, "0"),
      priority: "HIGH",
      text: `Bottleneck tersisa di ${formatStationLabel(flow.residual_bottleneck)} — perlu tindakan lanjutan.`,
      impactBadge: `${scenario.metrics.bottleneck_count.after} titik`,
    });
  }

  if (items.length === 0) {
    items.push({
      id: "stable",
      rank: "01",
      priority: "LOW",
      text: "Konfigurasi saat ini sudah optimal menurut policy RL; tidak ada perubahan yang direkomendasikan.",
      impactBadge: "Stabil",
    });
  }

  return items;
}

export function mapRlScenarioToScenarioData(
  scenario: RlScenario,
  index: number
): ScenarioData {
  const metrics = scenario.metrics;
  const constraints = scenario.constraints;

  const throughputBefore = metrics.throughput_per_hour.before ?? 0;
  const costBefore = metrics.total_op_cost_per_hour_rp.before ?? 0;

  return {
    id: scenario.scenario_id,
    tabNumber: index + 1,
    title: scenario.title.toUpperCase(),
    shortTitle: `${index + 1} ${scenario.title.toUpperCase()}`,
    subtitle: scenario.description,
    constraints: {
      hiring: constraints.hiring_allowed,
      fireMut: constraints.fire_or_mutation_allowed,
      automation: constraints.automation_allowed,
      budgetLabel: formatBudgetLabel(constraints.capex_rp),
    },
    metrics: {
      throughput: {
        diff: formatDelta(metrics.throughput_per_hour.delta_pct),
        diffType: diffType(metrics.throughput_per_hour.is_improvement),
        before: `${throughputBefore.toLocaleString("id-ID")}/jam`,
        after: `${metrics.throughput_per_hour.after.toLocaleString("id-ID")}/jam`,
      },
      errorRate: {
        diff: formatDelta(metrics.human_error_rate_pct.delta_pct),
        diffType: diffType(metrics.human_error_rate_pct.is_improvement),
        before: `${(metrics.human_error_rate_pct.before ?? 0).toFixed(2)}%`,
        after: `${metrics.human_error_rate_pct.after.toFixed(2)}%`,
      },
      opCost: {
        diff: formatDelta(metrics.total_op_cost_per_hour_rp.delta_pct),
        diffType: diffType(metrics.total_op_cost_per_hour_rp.is_improvement),
        before: `${formatRupiahShort(costBefore)}/jam`,
        after: `${formatRupiahShort(metrics.total_op_cost_per_hour_rp.after)}/jam`,
      },
    },
    shiftChart: {
      labels: SHIFT_LABELS,
      before: buildSeries(throughputBefore),
      after: buildSeries(metrics.throughput_per_hour.after),
    },
    costChart: {
      categories: COST_CATEGORIES,
      before: buildCostSeries(costBefore),
      after: buildCostSeries(metrics.total_op_cost_per_hour_rp.after),
    },
    stations: buildStations(scenario),
    graphSubtitle: scenario.insight,
    flowGraph: buildFlowGraph(scenario),
    recommendations: buildRecommendations(scenario),
    initialBotMessage: `Skenario "${scenario.title}" dihasilkan Maskable PPO dengan episode reward ${scenario.episode_reward}. Silakan tanyakan detail trade-off-nya.`,
    quickScenarios: [
      "Kenapa skenario ini direkomendasikan?",
      "Apa risiko burnout setelah rotasi?",
      "Berapa payback period capex-nya?",
    ],
  };
}