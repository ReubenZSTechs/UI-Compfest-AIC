# Rencana Pengembangan Frontend: Interactive Canvas Workspace

Dokumen ini merangkum arsitektur, alur kerja (workflow), dan langkah-langkah implementasi untuk merombak antarmuka pengguna menjadi sistem *Interactive Canvas* (mirip Miro). Perubahan ini mengubah paradigma aplikasi dari *Parser-Driven* menjadi *Canvas-First*, memberikan kebebasan penuh bagi pengguna untuk menyusun simulasi pabrik sebelum dieksekusi oleh AI.

---

## 1. Konsep Utama & Arsitektur

Prinsip dasar dari pembaruan ini adalah **Pemisahan Visual State dan LLM Payload**.
Frontend bertindak sebagai *Draft Zone* tempat pengguna bebas bereksperimen, sementara AI bertindak sebagai *Eksekutor* yang hanya dipanggil ketika pengguna sudah yakin dengan susunannya.

* **Visual State (Frontend Lokal):** Menyimpan koordinat ($X, Y$), warna, *zoom level*, *undo/redo stack*, dan mode alat (*toolbar*).
* **LLM Payload State (Backend/AI):** Menyimpan *Graph Data* murni (ID, teks/label, keahlian, dan koneksi relasional antar-node) tanpa terdistraksi oleh data visual.

---

## 2. Alur Pengguna (User Flow)

Pengalaman pengguna dibagi menjadi dua halaman utama untuk memastikan fokus maksimal.

1. **Halaman 1: Introduction (`/intro`)**
* Menggunakan *layout* bawaan (`AppShell`).
* Berisi pengenalan aplikasi, panduan singkat, dan pilihan *template* (Kanvas Kosong, Alur Seri, Alur Paralel).
* Terdapat tombol *Call-to-Action* (CTA): "Mulai Desain Canvas".


2. **Halaman 2: Full Canvas Workspace (`/canvas`)**
* *Full-screen* tanpa Sidebar bawaan.
* **Area Tengah:** Papan tulis interaktif untuk *drag & drop*.
* **Sisi Kiri:** *Toolbar* alat (Select, Add Process, Add Worker, Connect, Erase, Undo).
* **Sisi Kanan:** *Sidebar / Drawer* melayang untuk melihat/mengedit detail node (menggunakan komponen lama seperti `WorkerCard` atau `JobDeskTable`).
* **Sisi Atas:** *Topbar* berisi judul proyek dan tombol eksekusi "Mulai Analisis AI".


3. **Eksekusi (Analisis AI)**
* Pengguna menyusun node secara seri (A $\rightarrow$ B $\rightarrow$ C) atau paralel (A $\rightarrow$ B dan A $\rightarrow$ C).
* Saat menekan "Mulai Analisis AI", *frontend* mengkompilasi data canvas, membuang koordinat visual, dan mengirim JSON bersih ke *backend*.
* Canvas akan memberikan *feedback* visual (contoh: warna *border* node berubah sesuai status proses AI).



---

## 3. Struktur Data Node & Edge

Model relasi menggunakan pendekatan **Garis Penghubung (Edge/Connection)** karena lebih intuitif dan selaras dengan arsitektur JSON yang diharapkan oleh LLM.

### A. Format Ekstraksi Data (JSON Payload)

```json
{
  "factory_graph": {
    "nodes": [
      {
        "id": "process-1",
        "type": "process",
        "label": "Pemotongan Bahan",
        "required_skills": ["Cutting"]
      },
      {
        "id": "worker-1",
        "type": "worker",
        "label": "Arif Nugroho",
        "skills": ["Sewing", "Cutting"],
        "fatigue_score": 15
      }
    ],
    "edges": [
      { "source": "process-1", "target": "process-2", "type": "FLOW" },
      { "source": "worker-1", "target": "process-1", "type": "ASSIGNED_TO" }
    ]
  }
}

```

---

## 4. Konfigurasi Routing

Struktur *router* memisahkan halaman yang membutuhkan antarmuka *AppShell* lama dengan halaman *Canvas* yang membutuhkan layar penuh.

```tsx
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/app/router/ProtectedRoute";

import { IntroPage } from "@/pages/IntroPage";
import { CanvasPage } from "@/pages/CanvasPage";
import { DocumentParserPage } from "@/pages/Documentparserpage";
import { DigitalTwinPage } from "@/pages/DigitalTwinPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { HumanFactorsPage } from "@/pages/HumanFactorsPage";
import { SimulationPage } from "@/pages/SimulationPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const ROUTES = {
  LOGIN: "/login",
  INTRO: "/intro",
  CANVAS: "/canvas",
  PARSER: "/parser",
  DIGITAL_TWIN: "/digital-twin",
  DASHBOARD: "/dashboard",
  SIMULATION: "/simulation",
  HUMAN_FACTORS: "/human-factors",
} as const;

export const router = createBrowserRouter([
  {
    path: ROUTES.LOGIN,
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />, 
    children: [
      {
        // Route untuk Workspace Canvas (Full-Screen, tanpa AppShell)
        path: ROUTES.CANVAS,
        element: <CanvasPage />,
      },
      {
        // Route untuk halaman dengan Layout Bawaan
        element: <AppShell />, 
        children: [
          {
            path: "/",
            element: <Navigate to={ROUTES.INTRO} replace />,
          },
          {
            path: ROUTES.INTRO,
            element: <IntroPage />,
          },
          {
            path: ROUTES.PARSER,
            element: <DocumentParserPage />,
          },
          {
            path: ROUTES.DIGITAL_TWIN,
            element: <DigitalTwinPage />,
          },
          {
            path: ROUTES.DASHBOARD,
            element: <DashboardPage />,
          },
          {
            path: ROUTES.SIMULATION,
            element: <SimulationPage />,
          },
          {
            path: ROUTES.HUMAN_FACTORS,
            element: <HumanFactorsPage />,
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);

```

---

## 5. Tahapan Implementasi Frontend

* **Fase 1: Penyiapan Routing & Halaman Dasar**
* Buat `IntroPage.tsx` dan `CanvasPage.tsx`.
* Terapkan konfigurasi *router* di atas.


* **Fase 2: Integrasi Library Canvas & Custom Nodes**
* Pasang library *React Flow* (atau *XYFlow*) pada `CanvasPage.tsx`.
* Bungkus (*wrap*) UI komponen lama seperti `WorkerCard` dan `JobDeskTable` ke dalam *Custom Node* React Flow dengan menambahkan titik konektor (*handles*).
* Buat `Toolbar.tsx` di sisi kiri untuk mengatur state alat (`activeTool`).


* **Fase 3: Logika Relasi (Edge Connection)**
* Aktifkan fitur tarik garis (*drag & drop connections*) antar node.
* Bedakan tipe garis (contoh: seri/paralel menggunakan garis `FLOW`, penugasan pekerja menggunakan garis `ASSIGNED_TO`).


* **Fase 4: Pembuatan JSON Extractor & API Integration**
* Buat fungsi utilitas untuk merangkum `nodes` dan `edges` menjadi JSON payload yang membuang data koordinat visual.
* Sambungkan fungsi ini ke tombol "Analisis AI" untuk dikirim ke *backend*.


* **Fase 5: Animasi & Feedback Visual**
* Gunakan respons dari *backend* / AI untuk mengubah properti CSS node di *canvas* secara *real-time* (misal: penambahan *border* hijau ketika proses pada node tersebut selesai diverifikasi oleh AI).
