// // frontend/src/features/canvas/utils/runCanvasAnalysis.ts
// // Logika menjalankan analisis AI pada graph canvas saat ini.
// // Dipakai bersama oleh panel "Mulai Analisis AI" (Live) dan agent chatbot
// // (Agent), sehingga status & feedback visual node selalu sinkron lewat store.
// import { useCanvasUIStore } from "@/store/canvasUI";
// import { buildFactoryGraphPayload } from "./graphExtractor";
// import { computeExecutionRounds, toFlowGraph } from "./flowLogic";
// import { analyzeFactoryGraph } from "../api/canvasApi";

// const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// export interface CanvasAnalysisResult {
//   status: "done" | "error";
//   message: string;
// }

// export async function runCanvasAnalysis(signal?: AbortSignal): Promise<CanvasAnalysisResult> {
//   const store = useCanvasUIStore.getState();
//   const { nodes, edges } = store;
//   const payload = buildFactoryGraphPayload(nodes, edges);
//   const executionRounds = computeExecutionRounds(toFlowGraph(nodes, edges));

//   store.setAnalysis({ status: "running", message: "Mengompilasi graph & mengirim ke AI..." });
//   for (const node of nodes) {
//     store.updateNodeData(node.id, { aiStatus: "analyzing" });
//   }

//   try {
//     const response = await analyzeFactoryGraph({ ...payload, operational_limits: store.operationalLimits });

//     // Feedback visual mengikuti jadwal eksekusi: node dalam round yang sama
//     // (Parallel Split / AND-Join) ditandai bersamaan, round berikutnya menunggu.
//     const verifiedIds = new Set(response.verified_node_ids ?? []);
//     for (const round of executionRounds) {
//       if (signal?.aborted) {
//         return { status: "error", message: "Analisis dibatalkan." };
//       }
//       const roundIds = round.filter((id) => verifiedIds.has(id));
//       if (roundIds.length === 0) continue;

//       for (const id of roundIds) {
//         store.updateNodeData(id, { aiStatus: "analyzing" });
//       }
//       await delay(320);

//       if (signal?.aborted) {
//         return { status: "error", message: "Analisis dibatalkan." };
//       }

//       for (const id of roundIds) {
//         store.updateNodeData(id, { aiStatus: "verified" });
//       }
//       await delay(180);
//     }

//     // Pastikan semua node terverifikasi (termasuk node output di luar jadwal
//     // eksekusi proses) diberi status verified; sisanya dikembalikan ke idle.
//     for (const node of nodes) {
//       store.updateNodeData(node.id, { aiStatus: verifiedIds.has(node.id) ? "verified" : "idle" });
//     }

//     const message = response.message ?? "Analisis selesai.";
//     store.setAnalysis({ status: "done", message, finishedAt: new Date().toISOString() });
//     return { status: "done", message };
//   } catch (err) {
//     for (const node of nodes) {
//       store.updateNodeData(node.id, { aiStatus: "error" });
//     }
//     const message = err instanceof Error ? err.message : "Analisis gagal.";
//     store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
//     return { status: "error", message };
//   }
// }