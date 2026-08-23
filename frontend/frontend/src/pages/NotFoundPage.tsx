import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 text-center">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl">
        {/* 404 Icon / Code */}
        <div className="w-16 h-16 bg-blue-500/10 text-blue-400 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-blue-500/20">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <h1 className="text-4xl font-extrabold text-white tracking-tight">404</h1>
        <h2 className="text-lg font-semibold text-slate-200 mt-2">Halaman Tidak Ditemukan</h2>
        <p className="text-slate-400 text-sm mt-2">
          Maaf, halaman yang Anda cari tidak ada atau jalurnya salah.
        </p>

        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center w-full px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg text-sm transition-colors shadow-lg shadow-blue-600/20"
          >
            Kembali ke Beranda
          </Link>
        </div>
      </div>
    </div>
  );
}

// Export default disiapkan untuk keamanan import
export default NotFoundPage;