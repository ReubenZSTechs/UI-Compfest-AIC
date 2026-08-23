export function HumanFactorsPage() {
  const metrics = [
    { title: "Ergonomic Risk Score", value: "Low (1.2)", status: "Good", color: "text-emerald-400" },
    { title: "Operator Fatigue Index", value: "18%", status: "Optimal", color: "text-blue-400" },
    { title: "Workstation Safety", value: "96%", status: "Compliant", color: "text-emerald-400" },
  ];

  const operatorData = [
    { id: "OP-101", station: "Assembly Line A", postureScore: "98%", status: "Safe" },
    { id: "OP-102", station: "Packaging Station 2", postureScore: "85%", status: "Attention" },
    { id: "OP-103", station: "Quality Check B", postureScore: "94%", status: "Safe" },
  ];

  return (
    <div className="p-6 space-y-6 text-slate-100">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Human Factors & Ergonomics</h1>
        <p className="text-slate-400 text-sm mt-1">
          Analisis beban kerja, postur, dan tingkat kelelahan operator di lingkungan produksi.
        </p>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {metrics.map((item, index) => (
          <div key={index} className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
            <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">
              {item.title}
            </div>
            <div className={`text-3xl font-bold mt-2 ${item.color}`}>{item.value}</div>
            <div className="text-xs text-slate-400 mt-2">Status: {item.status}</div>
          </div>
        ))}
      </div>

      {/* Operator Posture & Ergonomics Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-4 text-white">Monitoring Postur Stasiun Kerja</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-800/60 text-slate-400 text-xs uppercase tracking-wider">
              <tr>
                <th className="p-3 rounded-l-lg">Operator ID</th>
                <th className="p-3">Stasiun Kerja</th>
                <th className="p-3">Skor Postur (RULA/REBA)</th>
                <th className="p-3 rounded-r-lg">Status Ergonomi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {operatorData.map((op) => (
                <tr key={op.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-3 font-medium text-white">{op.id}</td>
                  <td className="p-3">{op.station}</td>
                  <td className="p-3">{op.postureScore}</td>
                  <td className="p-3">
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                        op.status === "Safe"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {op.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Export default disiapkan untuk fleksibilitas import
export default HumanFactorsPage;