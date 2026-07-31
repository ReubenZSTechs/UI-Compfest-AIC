import { Link } from "react-router-dom";

export function DashboardPage() {
  return (
    <div className="p-6 space-y-6 text-slate-100">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Overview Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            Selamat datang! Berikut ringkasan status dan akses cepat sistem PABRIKERS.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            to="/parser"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors inline-flex items-center gap-2"
          >
            <span>Mulai Parse Dokumen</span>
          </Link>
        </div>
      </div>

      {/* Metrics Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">
            Dokumen Diproses
          </div>
          <div className="text-3xl font-bold mt-2 text-white">128</div>
          <div className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
            <span>↑ 12%</span>
            <span className="text-slate-500">dibanding minggu lalu</span>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">
            Digital Twin Active
          </div>
          <div className="text-3xl font-bold mt-2 text-white">12</div>
          <div className="text-xs text-slate-400 mt-2">
            Entitas tersinkronisasi
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">
            Akurasi Parsing
          </div>
          <div className="text-3xl font-bold mt-2 text-emerald-400">98.4%</div>
          <div className="text-xs text-slate-400 mt-2">
            Model AI Terkonfigurasi
          </div>
        </div>
      </div>

      {/* Quick Access Modules */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        <Link
          to="/parser"
          className="group bg-slate-900 border border-slate-800 hover:border-blue-500/50 p-6 rounded-xl transition-all"
        >
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">
            Document Parser &rarr;
          </h3>
          <p className="text-slate-400 text-sm mt-1">
            Ekstrak data dan tata letak dari dokumen teknis secara otomatis.
          </p>
        </Link>

        <Link
          to="/digital-twin"
          className="group bg-slate-900 border border-slate-800 hover:border-indigo-500/50 p-6 rounded-xl transition-all"
        >
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white group-hover:text-indigo-400 transition-colors">
            Digital Twin &rarr;
          </h3>
          <p className="text-slate-400 text-sm mt-1">
            Lihat visualisasi dan simulasi entitas pabrik secara real-time.
          </p>
        </Link>
      </div>
    </div>
  );
}

// Export default disiapkan untuk keamanan import
export default DashboardPage;   