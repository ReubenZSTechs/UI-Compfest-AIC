import { useState } from "react";

export function SimulationPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [simSpeed, setSimSpeed] = useState("1x");

  const simulationParams = [
    { label: "Target Production", value: "1,200 units/day" },
    { label: "Estimated Bottleneck", value: "Assembly Station 3" },
    { label: "Energy Consumption", value: "420 kWh" },
  ];

  return (
    <div className="p-6 space-y-6 text-slate-100">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Factory Process Simulation</h1>
          <p className="text-slate-400 text-sm mt-1">
            Simulasi alur kerja dan skenario beban produksi berbasis Digital Twin.
          </p>
        </div>

        {/* Simulation Action Bar */}
        <div className="flex items-center gap-3">
          <select
            value={simSpeed}
            onChange={(e) => setSimSpeed(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
          >
            <option value="0.5x font-mono">0.5x Speed</option>
            <option value="1x">1.0x Speed</option>
            <option value="2x">2.0x Speed</option>
            <option value="5x">5.0x Speed</option>
          </select>

          <button
            type="button"
            onClick={() => setIsRunning(!isRunning)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              isRunning
                ? "bg-amber-600 hover:bg-amber-500 text-white"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            }`}
          >
            <span>{isRunning ? "Pause Simulation" : "Start Simulation"}</span>
          </button>
        </div>
      </div>

      {/* Simulation Viewport Placeholder */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 flex flex-col items-center justify-center min-h-[360px] text-center relative overflow-hidden">
        {/* Status Indicator Badge */}
        <div className="absolute top-4 left-4">
          <span
            className={`text-xs px-3 py-1 rounded-full font-medium border flex items-center gap-2 ${
              isRunning
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-slate-800 text-slate-400 border-slate-700"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isRunning ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
              }`}
            />
            {isRunning ? `Simulating (${simSpeed})` : "Simulation Paused"}
          </span>
        </div>

        {/* Viewport Content */}
        <div className="w-16 h-16 rounded-2xl bg-slate-800 text-blue-400 flex items-center justify-center mb-4 border border-slate-700">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-white">3D / Node Canvas Visualizer</h3>
        <p className="text-slate-400 text-sm max-w-md mt-1">
          {isRunning
            ? "Simulasi alur produksi sedang berjalan secara virtual..."
            : "Tekan 'Start Simulation' untuk menjalankan kalkulasi alur kerja dan prediksi kemacetan."}
        </p>
      </div>

      {/* Parameter Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {simulationParams.map((param, index) => (
          <div key={index} className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
            <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">
              {param.label}
            </div>
            <div className="text-xl font-bold mt-2 text-white">{param.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Export default disiapkan untuk keamanan import
export default SimulationPage;