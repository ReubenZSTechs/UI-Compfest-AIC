# Dokumentasi Integrasi Frontend, Backend, & Engine AI/LLM

**Target Pembaca:** Backend Developer & AI/LLM Engineer
**Tujuan Dokumen:** Menyelaraskan kontrak data, arsitektur integrasi, dan filosofi interaksi antara UI interaktif (Frontend) dengan kapabilitas analitik/simulasi (Backend & AI).

---

## 1. Ringkasan Arsitektur & Filosofi Sistem

### A. Pemisahan Tegas "Visual State" vs "Clean Graph / LLM Payload"
Sistem ini membedakan secara ketat antara representasi visual kanvas dan data yang dikirim ke AI. 
- **Visual State (Hanya Frontend):** Data koordinat `(x, y)`, status seleksi, properti drag-and-drop, level zoom, dan metadata rendering React Flow. Data ini **TIDAK PERNAH** dikirim ke backend/LLM untuk menghemat token dan menghindari kebingungan model AI.
- **Clean Graph (LLM Payload):** Sebelum data dikirim ke backend, Frontend melakukan ekstraksi. `Nodes` dan `Edges` dibersihkan dan hanya menyisakan atribut esensial (ID, tipe operasi, constraint, relasi `FLOW` (proses-ke-proses) dan `ASSIGNED_TO` (pekerja-ke-proses)).

### B. Skema Unified Project Session (`ProjectDraft`)
Aplikasi ini beroperasi di atas arsitektur *Single Source of Truth* bernama `ProjectDraft`. 
Satu `projectId` membungkus seluruh tahapan:
1. Konfigurasi Awal (Template)
2. Desain Layout Pabrik (Canvas Nodes & Edges)
3. Interaksi AI & Context (Agent Chat History)
4. Parameter Operasional (Operational Constraints)
5. Hasil Optimasi AI (Optimization Cards)

Skema ini menjamin bahwa ketika user berpindah halaman atau me-refresh browser, seluruh *context* AI tetap sinkron tanpa perlu pengiriman ulang payload secara redundan.

---

## 2. Rincian Per Halaman (Page-by-Page Data & Contract)

### 2.1 `/intro` (Template Selection & Sesi Awal)
**Peran:** Entry point pengguna untuk membuat `ProjectDraft` baru berdasarkan template kosong, seri, atau paralel.
- **Request / Payload:** Tidak ada panggilan API berat. Hanya inisialisasi sesi lokal.
- **LLM Processing:** Tidak ada.

### 2.2 `/canvas` atau `/live` (Interactive Workspace & Graph Extraction)
**Peran:** Ruang kerja interaktif tempat pengguna mendesain lini produksi (Proses, Pekerja, Output) dan relasinya. Aksi "Mulai Analisis AI" dieksekusi di sini.
- **Request Body (JSON):**
  ```json
  {
    "projectId": "proj_draft_123xyz",
    "nodes": [
      { "id": "process-1", "kind": "process", "label": "Assembly", "requiredSkills": ["welding"] },
      { "id": "worker-1", "kind": "worker", "worker": { "skills": ["welding"], "fatigueScore": 12 } }
    ],
    "edges": [
      { "source": "worker-1", "target": "process-1", "relation": "ASSIGNED_TO" }
    ],
    "operational_limits": { "budgetLimit": 50000000, "allowOvertime": false }
  }
  ```
- **Response (JSON):**
  ```json
  {
    "status": "success",
    "verified_node_ids": ["process-1", "worker-1"],
    "message": "Graph tervalidasi. 1 pekerja dialokasikan dengan tepat.",
    "analysis_summary": "Pekerja-1 cocok untuk Assembly. Tidak ada bottleneck terdeteksi."
  }
  ```
- **LLM Processing (Task):** LLM bertugas membaca graf spasial yang telah diubah ke topologi relasional, memeriksa apakah *skills* pekerja cocok dengan *requiredSkills* proses, mendeteksi *dead-ends*, dan memverifikasi kelayakan alur secara logis.

### 2.3 `/agent` (AI Assistant, Contextual Chat, & Operational Settings)
**Peran:** Chatbot AI interaktif. Asisten ini memiliki konteks penuh terhadap graf kanvas saat ini dan batasan operasional.
- **Request Body (JSON):**
  ```json
  {
    "projectId": "proj_draft_123xyz",
    "message": "Apakah aman jika saya menambah shift lembur untuk lini Assembly?",
    "history": [ { "role": "assistant", "content": "Halo, ada yang bisa saya bantu terkait lini produksimu?" } ],
    "context": {
      "graph_snapshot": { /* Clean Graph */ },
      "operational_limits": { "allowOvertime": false }
    }
  }
  ```
- **Response (JSON):**
  ```json
  {
    "reply": "Berdasarkan pengaturan Anda saat ini, lembur (overtime) tidak diizinkan. Namun, lini Assembly memiliki tingkat utilisasi 95%. Jika Anda mengaktifkan lembur, throughput dapat meningkat sebesar 12%. Ingin saya buatkan simulasinya?"
  }
  ```
- **LLM Processing (Task):** Menganalisis pertanyaan user dengan merujuk pada `graph_snapshot` dan `operational_limits`. LLM harus memberikan saran berbasis data teknis pabrik tersebut.

### 2.4 `/project/:id/recommendations` (AI Optimization Scenarios & Scenario Cards)
**Peran:** Menerima *Clean Graph* yang sudah diverifikasi dan meminta AI menghasilkan 3 Skenario Optimasi (Card) dengan pendekatan RL (Reinforcement Learning) atau Heuristik.
- **Request Body (JSON):** Sama seperti `/canvas` extraction.
- **Response (JSON):** Array of `OptimizationCard` (Lihat Skema Data di Bagian 3).
- **LLM Processing (Task):** Menghitung *reward function* (Throughput maksimal, biaya minimal, fatigue minimal) dan menghasilkan 3 opsi trade-off (misal: "Budget Minim", "Throughput Maksimal", "Balanced").

### 2.5 `/project/:id/recommendation/:cardId` (Execution & Budget Allocation)
**Peran:** Menampilkan visualisasi mendalam (Chart Throughput, Cost Breakdown, Node Status) dari satu skenario spesifik sebelum dieksekusi, beserta interaksi *What-If*.
- **Request/Response:** Dirender secara visual dari hasil `/recommendations`. Simulasi chat "What-If" dikirim ke AI.
- **LLM Processing (Task):** Bertindak sebagai agen *What-If* yang mengalkulasi ulang metrik (RL recalculation) ketika user mengubah parameter skenario secara dinamis.

### 2.6 `/digital-twin` (Monitoring, Real-time Simulation, Shift Scheduling & Human Factors)
**Peran:** Memonitor kondisi riil (simulasi) pabrik yang sedang berjalan, melacak pergerakan inventori (WIP), utilitas mesin, dan kelelahan (fatigue) pekerja.
- **Protokol:** Koneksi persisten via **WebSocket**.
- **Payload WSS (Backend -> Frontend):** Mengirim *Tick* data real-time (Lihat Bagian 4).
- **LLM Processing:** AI bertindak sebagai *Anomaly Detector* di background. Jika mendeteksi lonjakan *Fatigue Score* atau penurunan drastis *Throughput*, AI memicu alert rekomendasi *Human Factors*.

### 2.7 `/document-parser` (Multi-stage Document & CV Ingestion)
**Peran:** Mengekstrak PDF/Dokumen (mis. CV Pekerja atau SOP Mesin) menjadi JSON terstruktur untuk diinjeksi ke dalam kanvas (sebagai Node Worker atau konfigurasi Mesin).
- **Request Body (Multipart Form-Data):** File PDF/Image.
- **Response (JSON):**
  ```json
  {
    "type": "worker_profile",
    "data": {
      "name": "Budi Santoso",
      "demographics": { "age": 34, "yearsOfExperience": 8 },
      "skills": ["welding", "quality_control"]
    }
  }
  ```
- **LLM Processing (Task):** Multi-modal OCR dan ekstraksi entitas berskema ketat (*Structured Output*), mengabaikan informasi non-esensial dan menangkap *skills* & *fatigue baseline*.

### 2.8 `/dashboard` (Registry & Hydration of Saved Drafts)
**Peran:** Mengambil daftar proyek tersimpan pengguna.
- **Request:** `GET /api/v1/projects`
- **Response:** Array of `ProjectDraft` (Metadata only).

---

## 3. Data Models & JSON Schemas

### A. Skema Factory Graph (Clean Payload)
```typescript
interface GraphPayload {
  nodes: Array<{
    id: string;
    type: "process" | "worker" | "output";
    // Jika type == process
    label?: string;
    requiredSkills?: string[];
    // Jika type == worker
    workerProfile?: {
      skills: string[];
      fatigueScore: number;
    }
  }>;
  edges: Array<{
    source: string;
    target: string;
    relation: "FLOW" | "ASSIGNED_TO"; // FLOW antar proses. ASSIGNED_TO dari pekerja ke proses.
    flowType?: "serial" | "parallel";
  }>;
}
```

### B. Skema Human Factors
Digunakan untuk Digital Twin & Analitik Kinerja Pekerja.
```typescript
interface HumanFactorsData {
  workerId: string;
  metrics: {
    fatigueScore: number;        // 0-100
    stressLevel: number;         // 0-100
    ergonomicRiskRULA: number;   // 1-7 (1-2 aman, 7 bahaya)
    burnoutProbability: number;  // 0.0 - 1.0
  };
  shiftContext: {
    hoursWorkedToday: number;
    consecutiveShifts: number;
  };
}
```

### C. Skema Operational Constraints
Batasan yang diberikan pada Agen LLM/RL.
```typescript
interface OperationalLimits {
  allowRecruitNewEmployees: boolean;
  allowOvertime: boolean;
  allowOutsourcing: boolean;
  budgetLimit: number; // Dalam IDR
}
```

### D. Skema Simulation State & Shift Schedules (Tick-based)
```typescript
interface SimulationTick {
  timestamp: string;
  tickId: number;
  metrics: {
    throughputPerHour: number;
    wipInventory: number;
  };
  nodesData: Array<{
    nodeId: string;
    status: "idle" | "running" | "blocked" | "maintenance";
    utilization: number;
    backlogCount: number;
  }>;
  activeBottlenecks: string[]; // array of node IDs
}
```

---

## 4. Matriks REST API & WebSocket Protocol

### A. REST API Endpoints

| Method | Path | Deskripsi | Status Code |
|---|---|---|---|
| `POST` | `/api/v1/projects` | Menyimpan / Sinkronisasi `ProjectDraft` ke backend. | 200 OK / 201 Created |
| `GET` | `/api/v1/projects` | Mendapatkan daftar `ProjectDraft` pengguna. | 200 OK |
| `GET` | `/api/v1/projects/:id` | Mengambil state detail satu `ProjectDraft`. | 200 OK / 404 Not Found |
| `POST` | `/api/v1/analyze/graph` | Memvalidasi topologi graf kanvas secara logis. | 200 OK / 400 Bad Request |
| `POST` | `/api/v1/analyze/optimize`| Meminta 3 Skenario Optimasi (Card) dari LLM/RL Engine. | 200 OK |
| `POST` | `/api/v1/chat/agent` | Mengirim pesan ke asisten AI dengan konteks pabrik. | 200 OK (Stream / JSON) |
| `POST` | `/api/v1/parser/document` | Mengunggah dokumen untuk di-parse menjadi entitas graf. | 200 OK / 422 Unprocessable |

### B. WebSocket Protocol (Digital Twin)

**Endpoint:** `wss://api.domain.com/v1/digital-twin/stream?projectId={projectId}`

**Payload Format (Server to Client - Tick Update):**
```json
{
  "event": "tick_update",
  "timestamp": "2026-08-14T10:00:00Z",
  "data": {
    "throughput_per_hour": 1450,
    "active_bottlenecks": ["process-3"],
    "worker_updates": [
      { "workerId": "worker-1", "fatigueScore": 45 }
    ]
  }
}
```

**Payload Format (Server to Client - AI Alert):**
```json
{
  "event": "ai_alert",
  "timestamp": "2026-08-14T10:05:00Z",
  "level": "critical",
  "data": {
    "message": "Ergonomic risk terdeteksi pada process-3 (RULA: 7). Pekerja berisiko cedera. Segera rotasi pekerja.",
    "targetIds": ["worker-1", "process-3"]
  }
}
```
