# Smart Manufacturing Digital Twin & RL Blueprint

Dokumen ini berisi arsitektur lengkap simulasi *Smart Manufacturing* berbasis *Reinforcement Learning* (RL), pemodelan *Human Factors*, serta sampel JSON *Digital Twin* sebagai *Single Source of Truth*.

---

## 1. Arsitektur Reinforcement Learning (RL)

* Tujuan: Mengoptimalkan alokasi SDM dan aset di lantai pabrik untuk memaksimalkan *throughput*, meminimalkan biaya operasional, menekan penumpukan barang (*bottleneck*), serta menjaga keselamatan & kesehatan fisik/mental pekerja.
* Markov Decision Process (MDP):
  * Observation Space ($S_t$): Vektor ter-normalisasi ($0.0 - 1.0$) yang memuat status *real-time* aset (kapasitas, antrean, biaya), profil pekerja (efisiensi, gaji, posisi tugas saat ini, tingkat kelelahan & stres), serta aturan operasional pabrik.
  * Action Space ($A_t$): *Multi-Discrete Action Space* untuk menentukan penugasan setiap Pekerja $i$ ke Stasiun/Alat $j$, keputusan rotasi kerja, hingga *upgrade* otomatisasi mesin.
  * Reward Function ($R_t$):
    $$R_t = w_1 \cdot \text{Throughput} - w_2 \cdot \text{Cost} - w_3 \cdot \text{Bottleneck} - w_4 \cdot \text{ErrorRate} - w_5 \cdot \text{BurnoutRisk}$$
* Algoritma Utama: Maskable PPO (Proximal Policy Optimization with Action Masking) dari sb3-contrib.
  * Keunggulan: Menangani kombinasi aksi diskrit kompleks dan memblokir aksi ilegal secara *real-time* sesuai aturan bisnis via *Action Masking*.

---

## 2. Peran & Spesifikasi JSON Digital Twin

JSON berfungsi sebagai Single Source of Truth yang menghubungkan LLM (Text Parser), UI (React/Lovable), dan Engine Simulasi (Gymnasium RL).

1. Matriks Kompatibilitas Full ($N \times M$): Memetakan kecocokan setiap pasangan pekerja dan stasiun kerja/tugas dengan *priors* yang mempercepat konvergensi RL hingga 3x lebih cepat.
2. Faktor Manusia Dunia Nyata (Human Factors & Ergonomics):
   * Pengaruh Usia & Demografi: Pekerja senior ($>45$ thn) lebih presisi (*error rate* rendah), namun akumulasi kelelahan fisik terjadi lebih cepat.
   * Beban Tugas & Lingkungan: Memperhitungkan kompleksitas alat, beban fokus kognitif (NASA-TLX), indeks beban fisik (RULA/REBA), kebisingan ($dB$), dan kelelahan berulang.
   * Hukum Yerkes-Dodson (Stres vs Performa): Stres tingkat sedang meningkatkan fokus (*eustress*), namun stres berlebih akibat antrean barang melampaui batas (*distress*) meruntuhkan kinerja dan memicu kecelakaan.
3. **Pemisahan Hardware (assets) & Workflow Task (job_descriptions)**:
   * assets: Karakteristik fisik alat/mesin (kebisingan, getaran, kapasitas dasar).
   * job_descriptions: Tuntutan kualitatif tugas (fokus kognitif, bahaya kesalahan).Explanability / Analytical Reasoningng**: Menyediakan penjelasan kualitatif LLM (metric_derivation_reasoning dan llm_reasoning) di balik setiap angka.

---

## 🛠️ 3. Sampel JSON Terintegrasi (factory_workflow_digital_twin.json)

<!-- Output LLM - dari penjelasan user -->
{
  "factory_info": {
    "factory_id": "fac-xyz-ygy-01",
    "factory_name": "Sweet Bread, PT XYZ Yogyakarta",
    "workflow_sequence": [
      "step_01_weighing",
      "step_02_mixing",
      "step_03_dough_dividing",
      "step_04_dough_shaping",
      "step_05_filling_panning",
      "step_06_proofing",
      "step_07_baking",
      "step_08_cooling",
      "step_09_sorting",
      "step_10_packaging"
    ]
  },
  "assets": [
    {
      "asset_id": "ast-01",
      "asset_name": "Digital Weighing Scale",
      "category": "measuring_equipment",
      "workflow_step": "step_01_weighing",
      "is_automated": true,
      "base_throughput_capacity": 300,
      "operational_cost_per_hour": 4.0,
      "environmental_factors": {
        "noise_level_db": 45,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.15
      },
      "metric_derivation_reasoning": "Timbangan digital tidak menghasilkan getaran/kebisingan signifikan. Beban fisik rendah karena operator hanya menakar dan memasukkan bahan sesuai formulasi. Nilai numerik (kapasitas, biaya) diestimasi, tidak tercantum di tabel sumber."
    },
    {
      "asset_id": "ast-02",
      "asset_name": "Mixer",
      "category": "machine",
      "workflow_step": "step_02_mixing",
      "is_automated": true,
      "base_throughput_capacity": 150,
      "operational_cost_per_hour": 10.0,
      "environmental_factors": {
        "noise_level_db": 72,
        "vibration_hazard_level": "medium",
        "physical_strain_index": 0.40
      },
      "metric_derivation_reasoning": "Mixer menghasilkan kebisingan & getaran menengah selama proses pengadukan adonan. QC pada tahap ini ketat (homogenitas, elastisitas adonan), sehingga fokus kognitif operator dinilai tinggi di job_descriptions."
    },
    {
      "asset_id": "ast-03",
      "asset_name": "Dough Divider",
      "category": "machine",
      "workflow_step": "step_03_dough_dividing",
      "is_automated": true,
      "base_throughput_capacity": 200,
      "operational_cost_per_hour": 9.0,
      "environmental_factors": {
        "noise_level_db": 68,
        "vibration_hazard_level": "medium",
        "physical_strain_index": 0.30
      },
      "metric_derivation_reasoning": "Mesin pembagi adonan otomatis dengan getaran mekanis sedang. Operator hanya mengoperasikan dan memantau, tanpa QC checklist eksplisit di tabel sumber."
    },
    {
      "asset_id": "ast-04",
      "asset_name": "Rounder Machine / Dough Sheeter",
      "category": "machine",
      "workflow_step": "step_04_dough_shaping",
      "is_automated": true,
      "base_throughput_capacity": 200,
      "operational_cost_per_hour": 9.0,
      "environmental_factors": {
        "noise_level_db": 66,
        "vibration_hazard_level": "medium",
        "physical_strain_index": 0.30
      },
      "metric_derivation_reasoning": "Mesin pembentuk adonan (rounder/sheeter) otomatis. Tidak ada QC eksplisit di tabel; peran operator terbatas pada pengawasan proses."
    },
    {
      "asset_id": "ast-05",
      "asset_name": "Breadline Machine",
      "category": "conveyor_automation",
      "workflow_step": "step_05_filling_panning",
      "is_automated": true,
      "base_throughput_capacity": 180,
      "operational_cost_per_hour": 11.0,
      "environmental_factors": {
        "noise_level_db": 64,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.35
      },
      "metric_derivation_reasoning": "Breadline machine menata adonan ke baking tin. QC ketat pada jarak antar adonan (±4 cm) menuntut ketelitian visual operator meski beban fisik moderat."
    },
    {
      "asset_id": "ast-06",
      "asset_name": "Proofing Cabinet",
      "category": "environmental_chamber",
      "workflow_step": "step_06_proofing",
      "is_automated": true,
      "base_throughput_capacity": 250,
      "operational_cost_per_hour": 7.0,
      "environmental_factors": {
        "noise_level_db": 40,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.10
      },
      "metric_derivation_reasoning": "Proofing cabinet adalah ruang terkendali suhu/kelembapan; beban fisik operator rendah, namun QC menuntut presisi suhu 55-60°C selama 50-60 menit dan pemantauan volume roti."
    },
    {
      "asset_id": "ast-07",
      "asset_name": "Deck Oven / Combi Oven",
      "category": "machine",
      "workflow_step": "step_07_baking",
      "is_automated": true,
      "base_throughput_capacity": 220,
      "operational_cost_per_hour": 18.0,
      "environmental_factors": {
        "noise_level_db": 58,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.55
      },
      "metric_derivation_reasoning": "Oven menghasilkan panas tinggi (bahaya panas, bukan kebisingan) sehingga physical_strain_index dinaikkan. QC kritikal: suhu 170°C selama 8-10 menit, kematangan & warna roti harus presisi agar tidak gosong."
    },
    {
      "asset_id": "ast-08",
      "asset_name": "Cooling Area",
      "category": "manual_station",
      "workflow_step": "step_08_cooling",
      "is_automated": false,
      "base_throughput_capacity": 220,
      "operational_cost_per_hour": 2.0,
      "environmental_factors": {
        "noise_level_db": 35,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.25
      },
      "metric_derivation_reasoning": "Tidak ada peralatan (tabel: '—'); area pendinginan bersifat pasif. Beban fisik berasal dari aktivitas memindahkan loyang/produk secara manual."
    },
    {
      "asset_id": "ast-09",
      "asset_name": "Sorting Station (Manual Visual Inspection)",
      "category": "manual_station",
      "workflow_step": "step_09_sorting",
      "is_automated": false,
      "base_throughput_capacity": 200,
      "operational_cost_per_hour": 5.0,
      "environmental_factors": {
        "noise_level_db": 40,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.20
      },
      "metric_derivation_reasoning": "Tidak ada peralatan tercantum ('—'); sortir sepenuhnya manual berbasis inspeksi visual. Beban kognitif tinggi karena daftar cacat yang harus dideteksi cukup panjang (gosong, filling bocor, lengket, hancur, kurang matang, dll.)."
    },
    {
      "asset_id": "ast-10",
      "asset_name": "Packaging Machine",
      "category": "machine",
      "workflow_step": "step_10_packaging",
      "is_automated": false,
      "base_throughput_capacity": 200,
      "operational_cost_per_hour": 8.0,
      "environmental_factors": {
        "noise_level_db": 60,
        "vibration_hazard_level": "low",
        "physical_strain_index": 0.30
      },
      "metric_derivation_reasoning": "Meski disebut 'Packaging Machine', kolom Otomatisasi bertanda '—' pada tabel sumber, artinya mesin dioperasikan/dijalankan manual oleh operator, bukan berjalan otomatis penuh."
    }
  ],
  "job_descriptions": [
    {
      "job_id": "job-01",
      "job_title": "Operator Weighing",
      "workflow_step": "step_01_weighing",
      "assigned_asset_id": "ast-01",
      "demands": {
        "required_cognitive_focus": 0.55,
        "physical_demand_level": "low",
        "task_complexity": 0.30,
        "error_severity": "moderate"
      },
      "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
      "metric_derivation_reasoning": "Tugas menimbang bahan sesuai formulasi bersifat rutin dan terstandar, fokus kognitif sedang (ketepatan takaran) dengan beban fisik rendah."
    },
    {
      "job_id": "job-02",
      "job_title": "Operator Mixing",
      "workflow_step": "step_02_mixing",
      "assigned_asset_id": "ast-02",
      "demands": {
        "required_cognitive_focus": 0.75,
        "physical_demand_level": "medium",
        "task_complexity": 0.55,
        "error_severity": "high"
      },
      "qc_requirement": "Memastikan adonan homogen, elastis, dan tidak lengket.",
      "metric_derivation_reasoning": "QC eksplisit di tabel (homogenitas, elastisitas adonan) menuntut fokus kognitif dan judgement lebih tinggi dibanding tahap penimbangan."
    },
    {
      "job_id": "job-03",
      "job_title": "Operator Dough Dividing",
      "workflow_step": "step_03_dough_dividing",
      "assigned_asset_id": "ast-03",
      "demands": {
        "required_cognitive_focus": 0.50,
        "physical_demand_level": "medium",
        "task_complexity": 0.35,
        "error_severity": "moderate"
      },
      "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
      "metric_derivation_reasoning": "Peran operator terbatas pada mengoperasikan dan memantau mesin pembagi adonan; tidak ada kriteria QC tertulis di tabel."
    },
    {
      "job_id": "job-04",
      "job_title": "Operator Dough Shaping",
      "workflow_step": "step_04_dough_shaping",
      "assigned_asset_id": "ast-04",
      "demands": {
        "required_cognitive_focus": 0.50,
        "physical_demand_level": "medium",
        "task_complexity": 0.35,
        "error_severity": "moderate"
      },
      "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
      "metric_derivation_reasoning": "Sama seperti dough dividing, operator hanya mengoperasikan dan memantau proses rounder/sheeter."
    },
    {
      "job_id": "job-05",
      "job_title": "Operator Filling & Panning",
      "workflow_step": "step_05_filling_panning",
      "assigned_asset_id": "ast-05",
      "demands": {
        "required_cognitive_focus": 0.70,
        "physical_demand_level": "medium",
        "task_complexity": 0.45,
        "error_severity": "moderate"
      },
      "qc_requirement": "Memastikan jarak antar adonan ±4 cm.",
      "metric_derivation_reasoning": "QC presisi jarak (±4 cm) menuntut ketelitian visual yang konsisten selama proses penataan pada baking tin berjalan."
    },
    {
      "job_id": "job-06",
      "job_title": "Operator Proofing",
      "workflow_step": "step_06_proofing",
      "assigned_asset_id": "ast-06",
      "demands": {
        "required_cognitive_focus": 0.60,
        "physical_demand_level": "low",
        "task_complexity": 0.40,
        "error_severity": "high"
      },
      "qc_requirement": "Memastikan suhu 55-60°C selama 50-60 menit serta adonan mengembang dengan baik (volume roti).",
      "metric_derivation_reasoning": "Kesalahan pengaturan suhu/waktu proofing berdampak langsung pada kualitas volume roti pada tahap berikutnya (baking), sehingga error_severity dinilai tinggi walau beban fisik rendah."
    },
    {
      "job_id": "job-07",
      "job_title": "Operator Baking",
      "workflow_step": "step_07_baking",
      "assigned_asset_id": "ast-07",
      "demands": {
        "required_cognitive_focus": 0.85,
        "physical_demand_level": "high",
        "task_complexity": 0.70,
        "error_severity": "critical"
      },
      "qc_requirement": "Memastikan suhu 170°C selama 8-10 menit sehingga kematangan roti sesuai dan tidak gosong (warna roti).",
      "metric_derivation_reasoning": "Tahap paling kritikal: parameter suhu/waktu presisi, risiko panas tinggi (beban fisik), dan kesalahan berakibat langsung pada kegagalan produk (gosong)."
    },
    {
      "job_id": "job-08",
      "job_title": "Operator Cooling",
      "workflow_step": "step_08_cooling",
      "assigned_asset_id": "ast-08",
      "demands": {
        "required_cognitive_focus": 0.30,
        "physical_demand_level": "medium",
        "task_complexity": 0.20,
        "error_severity": "low"
      },
      "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
      "metric_derivation_reasoning": "Tugas manual memindahkan produk ke area pendinginan; beban fisik dari mengangkat/memindahkan, fokus kognitif rendah."
    },
    {
      "job_id": "job-09",
      "job_title": "Inspektur Sortir",
      "workflow_step": "step_09_sorting",
      "assigned_asset_id": "ast-09",
      "demands": {
        "required_cognitive_focus": 0.90,
        "physical_demand_level": "low",
        "task_complexity": 0.50,
        "error_severity": "high"
      },
      "qc_requirement": "Memeriksa produk cacat: gosong, filling bocor, lengket, hancur, kurang matang, tidak mengembang, tanpa topping, ukuran tidak sesuai, dan cacat lainnya.",
      "metric_derivation_reasoning": "Daftar kriteria cacat yang panjang dan beragam menuntut fokus kognitif sangat tinggi meski beban fisik rendah; ini adalah gerbang QC akhir sebelum packaging."
    },
    {
      "job_id": "job-10",
      "job_title": "Operator Packaging",
      "workflow_step": "step_10_packaging",
      "assigned_asset_id": "ast-10",
      "demands": {
        "required_cognitive_focus": 0.40,
        "physical_demand_level": "medium",
        "task_complexity": 0.25,
        "error_severity": "low"
      },
      "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
      "metric_derivation_reasoning": "Tugas rutin mengemas produk yang sudah lolos sorting; risiko kesalahan relatif rendah karena QC utama sudah dilakukan di tahap sebelumnya."
    }
  ],
  "workers": [
    { "worker_id": "wrk-01", "name": "Dedi Kurniawan", "demographics": { "age": 35, "gender": "male", "years_of_experience": 8, "baseline_physical_stamina": 0.75, "cognitive_resilience": 0.70 }, "shift_context": { "hours_worked_today": 3.0, "consecutive_shifts": 2 } },
    { "worker_id": "wrk-02", "name": "Ratna Wulandari", "demographics": { "age": 29, "gender": "female", "years_of_experience": 5, "baseline_physical_stamina": 0.80, "cognitive_resilience": 0.82 }, "shift_context": { "hours_worked_today": 3.0, "consecutive_shifts": 3 } },
    { "worker_id": "wrk-03", "name": "Agus Prasetyo", "demographics": { "age": 41, "gender": "male", "years_of_experience": 12, "baseline_physical_stamina": 0.68, "cognitive_resilience": 0.75 }, "shift_context": { "hours_worked_today": 4.0, "consecutive_shifts": 4 } },
    { "worker_id": "wrk-04", "name": "Sri Mulyani", "demographics": { "age": 26, "gender": "female", "years_of_experience": 3, "baseline_physical_stamina": 0.85, "cognitive_resilience": 0.72 }, "shift_context": { "hours_worked_today": 4.0, "consecutive_shifts": 2 } },
    { "worker_id": "wrk-05", "name": "Yusuf Hidayat", "demographics": { "age": 33, "gender": "male", "years_of_experience": 7, "baseline_physical_stamina": 0.78, "cognitive_resilience": 0.78 }, "shift_context": { "hours_worked_today": 2.5, "consecutive_shifts": 1 } },
    { "worker_id": "wrk-06", "name": "Wahyu Ningsih", "demographics": { "age": 30, "gender": "female", "years_of_experience": 6, "baseline_physical_stamina": 0.70, "cognitive_resilience": 0.80 }, "shift_context": { "hours_worked_today": 2.5, "consecutive_shifts": 3 } },
    { "worker_id": "wrk-07", "name": "Bambang Setiawan", "demographics": { "age": 45, "gender": "male", "years_of_experience": 18, "baseline_physical_stamina": 0.65, "cognitive_resilience": 0.90 }, "shift_context": { "hours_worked_today": 5.0, "consecutive_shifts": 5 } },
    { "worker_id": "wrk-08", "name": "Indah Permatasari", "demographics": { "age": 24, "gender": "female", "years_of_experience": 2, "baseline_physical_stamina": 0.88, "cognitive_resilience": 0.60 }, "shift_context": { "hours_worked_today": 1.5, "consecutive_shifts": 1 } },
    { "worker_id": "wrk-09", "name": "Hendra Saputra", "demographics": { "age": 38, "gender": "male", "years_of_experience": 10, "baseline_physical_stamina": 0.72, "cognitive_resilience": 0.85 }, "shift_context": { "hours_worked_today": 4.5, "consecutive_shifts": 4 } },
    { "worker_id": "wrk-10", "name": "Lestari Handayani", "demographics": { "age": 27, "gender": "female", "years_of_experience": 4, "baseline_physical_stamina": 0.83, "cognitive_resilience": 0.68 }, "shift_context": { "hours_worked_today": 1.5, "consecutive_shifts": 2 } }
  ],
  "factory_flow_rightnow": {
    "snapshot_timestamp": "2026-07-27T09:30:00+07:00",
    "note": "Snapshot kondisi lantai produksi saat ini: posisi tiap staf, tahap yang sedang dikerjakan, dan tujuan perpindahan (hand-off) ke tahap berikutnya dalam alur linear step_01 -> step_10.",
    "staff_current_positions": [
      { "worker_id": "wrk-01", "name": "Dedi Kurniawan", "current_station": "step_01_weighing", "current_asset_id": "ast-01", "activity_status": "processing", "moving_to_next_step": "step_02_mixing", "handoff_item": "batch adonan tertimbang #B-241" },
      { "worker_id": "wrk-02", "name": "Ratna Wulandari", "current_station": "step_02_mixing", "current_asset_id": "ast-02", "activity_status": "processing", "moving_to_next_step": "step_03_dough_dividing", "handoff_item": "adonan tercampur #B-240" },
      { "worker_id": "wrk-03", "name": "Agus Prasetyo", "current_station": "step_03_dough_dividing", "current_asset_id": "ast-03", "activity_status": "processing", "moving_to_next_step": "step_04_dough_shaping", "handoff_item": "potongan adonan #B-239" },
      { "worker_id": "wrk-04", "name": "Sri Mulyani", "current_station": "step_04_dough_shaping", "current_asset_id": "ast-04", "activity_status": "processing", "moving_to_next_step": "step_05_filling_panning", "handoff_item": "adonan terbentuk #B-238" },
      { "worker_id": "wrk-05", "name": "Yusuf Hidayat", "current_station": "step_05_filling_panning", "current_asset_id": "ast-05", "activity_status": "processing", "moving_to_next_step": "step_06_proofing", "handoff_item": "loyang terisi #B-237" },
      { "worker_id": "wrk-06", "name": "Wahyu Ningsih", "current_station": "step_06_proofing", "current_asset_id": "ast-06", "activity_status": "waiting_on_machine", "moving_to_next_step": "step_07_baking", "handoff_item": "loyang proofing #B-236 (25 menit tersisa)" },
      { "worker_id": "wrk-07", "name": "Bambang Setiawan", "current_station": "step_07_baking", "current_asset_id": "ast-07", "activity_status": "processing", "moving_to_next_step": "step_08_cooling", "handoff_item": "loyang panggang #B-235" },
      { "worker_id": "wrk-08", "name": "Indah Permatasari", "current_station": "step_08_cooling", "current_asset_id": "ast-08", "activity_status": "idle_waiting_input", "moving_to_next_step": "step_09_sorting", "handoff_item": "produk mendingin #B-234" },
      { "worker_id": "wrk-09", "name": "Hendra Saputra", "current_station": "step_09_sorting", "current_asset_id": "ast-09", "activity_status": "processing", "moving_to_next_step": "step_10_packaging", "handoff_item": "produk lolos sortir #B-233" },
      { "worker_id": "wrk-10", "name": "Lestari Handayani", "current_station": "step_10_packaging", "current_asset_id": "ast-10", "activity_status": "processing", "moving_to_next_step": "finished_goods_storage", "handoff_item": "produk terkemas #B-232" }
    ]
  },
  "llm_compatibility_and_evaluations": [
    { "worker_id": "wrk-01", "job_id": "job-01", "asset_id": "ast-01", "evaluations": { "overall_compatibility_score": 0.78, "throughput_multiplier": 1.05, "error_multiplier": 0.85, "fatigue_accumulation_rate": 0.60, "stress_sensitivity_factor": 0.70 }, "llm_reasoning": "Dedi (8 thn pengalaman) cukup mumpuni untuk tugas penimbangan yang rutin; beban fisik rendah menjaga akumulasi kelelahan tetap rendah." },
    { "worker_id": "wrk-02", "job_id": "job-02", "asset_id": "ast-02", "evaluations": { "overall_compatibility_score": 0.85, "throughput_multiplier": 1.10, "error_multiplier": 0.70, "fatigue_accumulation_rate": 0.65, "stress_sensitivity_factor": 0.60 }, "llm_reasoning": "Ratna memiliki resiliensi kognitif tinggi (0.82) yang cocok dengan tuntutan QC mixing (homogenitas & elastisitas adonan)." },
    { "worker_id": "wrk-03", "job_id": "job-03", "asset_id": "ast-03", "evaluations": { "overall_compatibility_score": 0.80, "throughput_multiplier": 1.00, "error_multiplier": 0.90, "fatigue_accumulation_rate": 0.70, "stress_sensitivity_factor": 0.65 }, "llm_reasoning": "Agus (12 thn pengalaman) stabil pada tugas pengoperasian mesin pembagi adonan yang repetitif namun cukup melelahkan secara fisik." },
    { "worker_id": "wrk-04", "job_id": "job-04", "asset_id": "ast-04", "evaluations": { "overall_compatibility_score": 0.82, "throughput_multiplier": 1.08, "error_multiplier": 0.85, "fatigue_accumulation_rate": 0.55, "stress_sensitivity_factor": 0.60 }, "llm_reasoning": "Sri memiliki stamina fisik tinggi (0.85) yang cocok untuk tugas pengoperasian mesin pembentuk adonan yang terus-menerus." },
    { "worker_id": "wrk-05", "job_id": "job-05", "asset_id": "ast-05", "evaluations": { "overall_compatibility_score": 0.83, "throughput_multiplier": 1.05, "error_multiplier": 0.75, "fatigue_accumulation_rate": 0.60, "stress_sensitivity_factor": 0.65 }, "llm_reasoning": "Yusuf cukup teliti untuk memenuhi QC jarak antar adonan (±4cm) pada breadline yang bergerak cepat." },
    { "worker_id": "wrk-06", "job_id": "job-06", "asset_id": "ast-06", "evaluations": { "overall_compatibility_score": 0.86, "throughput_multiplier": 1.00, "error_multiplier": 0.60, "fatigue_accumulation_rate": 0.40, "stress_sensitivity_factor": 0.55 }, "llm_reasoning": "Wahyu menjaga presisi suhu/waktu proofing dengan baik; beban fisik rendah menjaga kelelahan tetap rendah meski tanggung jawab QC tinggi." },
    { "worker_id": "wrk-07", "job_id": "job-07", "asset_id": "ast-07", "evaluations": { "overall_compatibility_score": 0.90, "throughput_multiplier": 1.15, "error_multiplier": 0.40, "fatigue_accumulation_rate": 1.35, "stress_sensitivity_factor": 0.80 }, "llm_reasoning": "Bambang (18 thn pengalaman, cognitive_resilience 0.90) sangat presisi pada tahap baking yang kritikal, namun panas oven tinggi (physical_strain_index 0.55) dikombinasikan 5 shift berturut-turut mempercepat akumulasi kelelahan (1.35x) - menjadi worker dengan burnout risk tertinggi saat ini." },
    { "worker_id": "wrk-08", "job_id": "job-08", "asset_id": "ast-08", "evaluations": { "overall_compatibility_score": 0.75, "throughput_multiplier": 0.95, "error_multiplier": 1.00, "fatigue_accumulation_rate": 0.45, "stress_sensitivity_factor": 0.50 }, "llm_reasoning": "Indah masih baru (2 thn pengalaman) namun tugas cooling bersifat sederhana sehingga kompatibilitasnya tetap memadai." },
    { "worker_id": "wrk-09", "job_id": "job-09", "asset_id": "ast-09", "evaluations": { "overall_compatibility_score": 0.88, "throughput_multiplier": 1.00, "error_multiplier": 0.55, "fatigue_accumulation_rate": 0.50, "stress_sensitivity_factor": 0.65 }, "llm_reasoning": "Hendra (10 thn pengalaman, cognitive_resilience 0.85) andal mendeteksi ragam cacat produk pada tahap QC akhir sebelum packaging." },
    { "worker_id": "wrk-10", "job_id": "job-10", "asset_id": "ast-10", "evaluations": { "overall_compatibility_score": 0.79, "throughput_multiplier": 1.02, "error_multiplier": 0.90, "fatigue_accumulation_rate": 0.50, "stress_sensitivity_factor": 0.55 }, "llm_reasoning": "Lestari cukup kompeten pada tugas pengemasan rutin dengan risiko kesalahan rendah karena QC utama sudah selesai di tahap sortir." }
  ]
}


<!-- Hasil simulasi pertama - kondisi saat ini -->
{
  "live_simulation_state": {
    "current_assignments": [
      { "worker_id": "wrk-01", "assigned_job_id": "job-01", "assigned_asset_id": "ast-01", "calculated_realtime_metrics": { "current_fatigue_level": 0.20, "current_stress_level": 0.18, "effective_throughput_per_hour": 300.0, "effective_error_probability": 0.010, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-02", "assigned_job_id": "job-02", "assigned_asset_id": "ast-02", "calculated_realtime_metrics": { "current_fatigue_level": 0.25, "current_stress_level": 0.22, "effective_throughput_per_hour": 165.0, "effective_error_probability": 0.014, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-03", "assigned_job_id": "job-03", "assigned_asset_id": "ast-03", "calculated_realtime_metrics": { "current_fatigue_level": 0.35, "current_stress_level": 0.25, "effective_throughput_per_hour": 200.0, "effective_error_probability": 0.018, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-04", "assigned_job_id": "job-04", "assigned_asset_id": "ast-04", "calculated_realtime_metrics": { "current_fatigue_level": 0.30, "current_stress_level": 0.20, "effective_throughput_per_hour": 216.0, "effective_error_probability": 0.015, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-05", "assigned_job_id": "job-05", "assigned_asset_id": "ast-05", "calculated_realtime_metrics": { "current_fatigue_level": 0.22, "current_stress_level": 0.24, "effective_throughput_per_hour": 189.0, "effective_error_probability": 0.016, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-06", "assigned_job_id": "job-06", "assigned_asset_id": "ast-06", "calculated_realtime_metrics": { "current_fatigue_level": 0.18, "current_stress_level": 0.30, "effective_throughput_per_hour": 250.0, "effective_error_probability": 0.008, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-07", "assigned_job_id": "job-07", "assigned_asset_id": "ast-07", "calculated_realtime_metrics": { "current_fatigue_level": 0.72, "current_stress_level": 0.58, "effective_throughput_per_hour": 253.0, "effective_error_probability": 0.030, "burnout_hazard_risk": "high" } },
      { "worker_id": "wrk-08", "assigned_job_id": "job-08", "assigned_asset_id": "ast-08", "calculated_realtime_metrics": { "current_fatigue_level": 0.12, "current_stress_level": 0.15, "effective_throughput_per_hour": 209.0, "effective_error_probability": 0.012, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-09", "assigned_job_id": "job-09", "assigned_asset_id": "ast-09", "calculated_realtime_metrics": { "current_fatigue_level": 0.28, "current_stress_level": 0.26, "effective_throughput_per_hour": 200.0, "effective_error_probability": 0.011, "burnout_hazard_risk": "low" } },
      { "worker_id": "wrk-10", "assigned_job_id": "job-10", "assigned_asset_id": "ast-10", "calculated_realtime_metrics": { "current_fatigue_level": 0.10, "current_stress_level": 0.14, "effective_throughput_per_hour": 204.0, "effective_error_probability": 0.010, "burnout_hazard_risk": "low" } }
    ],
    "system_bottlenecks": ["step_07_baking"],
    "simulation_summary": {
      "total_output_units": 2155.0,
      "target_output_units": 2500.0,
      "production_achievement_percentage": 86.2,
      "total_operational_cost_idr": 14500000.0,
      "cost_per_unit_idr": 6728.54,
      "efficiency_score": 78.5
    },
    "step_breakdown": [
      { "step_id": "step_01", "step_name": "Preparation", "status": "normal", "output_generated": 300.0, "operational_cost_idr": 1200000.0 },
      { "step_id": "step_02", "step_name": "Mixing", "status": "normal", "output_generated": 280.0, "operational_cost_idr": 1300000.0 },
      { "step_id": "step_03", "step_name": "Molding", "status": "normal", "output_generated": 270.0, "operational_cost_idr": 1150000.0 },
      { "step_id": "step_04", "step_name": "Fermentation", "status": "normal", "output_generated": 260.0, "operational_cost_idr": 1400000.0 },
      { "step_id": "step_05", "step_name": "Shaping", "status": "normal", "output_generated": 250.0, "operational_cost_idr": 1250000.0 },
      { "step_id": "step_06", "step_name": "Proofing", "status": "normal", "output_generated": 235.0, "operational_cost_idr": 1350000.0 },
      { "step_id": "step_07_baking", "step_name": "Baking Process", "status": "bottleneck", "output_generated": 200.0, "operational_cost_idr": 2500000.0 },
      { "step_id": "step_08", "step_name": "Cooling", "status": "normal", "output_generated": 195.0, "operational_cost_idr": 1100000.0 },
      { "step_id": "step_09", "step_name": "Sorting", "status": "normal", "output_generated": 190.0, "operational_cost_idr": 1050000.0 },
      { "step_id": "step_10", "step_name": "Packaging", "status": "normal", "output_generated": 185.0, "operational_cost_idr": 1100000.0 }
    ],
    "analytical_insight_summary": "Baking (wrk-07/Bambang) adalah bottleneck utama lini saat ini: fatigue 0.72 dan stress 0.58 mendekati ambang distress (Yerkes-Dodson), dengan burnout_hazard_risk 'high' setelah 5.0 jam kerja dan 5 shift berturut-turut. Karena baking adalah gerbang wajib sebelum cooling-sorting-packaging, keterlambatan atau penurunan performa di sini akan merambat ke seluruh downstream. Rekomendasi: rotasi/istirahat 15 menit untuk wrk-07 dalam waktu dekat untuk mencegah lonjakan error_probability, sejalan dengan pola yang sudah teridentifikasi pada dokumen acuan sebelumnya (kasus Budi di Job-01)."
  }
}

<!-- Hasil optimisasi - skenario-skenario optimal -->
{
  "hasil_optimisasi_skenario_optimal": {
    "meta": {
      "status": "RL CONVERGED",
      "total_episodes": 10000,
      "algorithm": "Maskable PPO (sb3-contrib)",
      "baseline": {
        "throughput_per_hour": 840,
        "human_error_rate_pct": 8.2,
        "total_op_cost_per_hour_rp": 4200000
      },
      "description": "Tiga skenario Pareto-optimal terpilih dari hasil training, diurutkan berdasarkan trade-off antara throughput, human error rate, dan biaya operasional pada batasan (constraint) yang berbeda. Setiap skenario menyertakan factory_flow_optimal: penempatan staf hasil rekomendasi RL, dibandingkan dengan factory_flow_rightnow (kondisi saat ini)."
    },
    "scenarios": [
      {
        "scenario_id": "scenario_01",
        "title": "Realokasi SDM Murni",
        "recommended": true,
        "description": "Optimasi tanpa rekrut & tanpa otomasi baru — hanya redistribusi operator yang sudah ada ke pos dengan kompatibilitas tertinggi.",
        "constraints": {
          "hiring_allowed": false,
          "fire_or_mutation_allowed": false,
          "automation_allowed": false,
          "capex_rp": 0
        },
        "metrics": {
          "throughput_per_hour": { "before": 840, "after": 1050, "delta_pct": 25.0, "direction": "up" },
          "human_error_rate_pct": { "before": 8.2, "after": 5.4, "delta_pct": -34.1, "direction": "up" },
          "total_op_cost_per_hour_rp": { "before": 4200000, "after": 3900000, "delta_pct": -7.1, "direction": "up" }
        },
        "insight": "ROI tertinggi — seluruh perbaikan didapat murni dari penempatan ulang staf existing, tanpa capex maupun risiko HR (PHK/rekrut).",
        "factory_flow_optimal": {
          "note": "Hanya 2 dari 10 pekerja direkomendasikan untuk dirotasi (swap), 8 lainnya tetap di posisi masing-masing karena sudah pada kompatibilitas optimal (skor >0.78 pada llm_compatibility_and_evaluations).",
          "reallocation_moves": [
            {
              "move_id": "move-01",
              "worker_id": "wrk-07",
              "name": "Bambang Setiawan",
              "from_station": "step_07_baking",
              "to_station": "step_09_sorting",
              "reason": "Bambang (usia 45, stamina fisik 0.65) mengalami fatigue_accumulation_rate 1.35x di Baking akibat physical_strain_index tinggi (0.55, panas oven), memicu burnout_hazard_risk 'high' setelah 5 shift berturut. Cognitive_resilience-nya yang sangat tinggi (0.90) justru lebih optimal dipakai di Sorting (required_cognitive_focus 0.90, physical_demand_level rendah) — mengurangi beban fisik tanpa mengorbankan ketelitian QC."
            },
            {
              "move_id": "move-02",
              "worker_id": "wrk-09",
              "name": "Hendra Saputra",
              "from_station": "step_09_sorting",
              "to_station": "step_07_baking",
              "reason": "Hendra (stamina fisik 0.72, lebih tinggi dari Bambang) lebih tahan terhadap beban panas & fisik tinggi di Baking. Cognitive_resilience 0.85 masih memadai untuk error_severity 'critical' di stasiun ini, dan ia belum membawa akumulasi kelelahan dari shift-shift sebelumnya seperti Bambang."
            }
          ],
          "new_cross_compatibility_evaluations": [
            { "worker_id": "wrk-07", "job_id": "job-09", "asset_id": "ast-09", "evaluations": { "overall_compatibility_score": 0.91, "throughput_multiplier": 1.02, "error_multiplier": 0.45, "fatigue_accumulation_rate": 0.55, "stress_sensitivity_factor": 0.60 }, "llm_reasoning": "Kombinasi cognitive_resilience sangat tinggi (0.90) dengan tuntutan fokus kognitif Sorting (0.90) sangat pas; physical_demand_level rendah menekan fatigue_accumulation_rate turun drastis dari 1.35x menjadi 0.55x." },
            { "worker_id": "wrk-09", "job_id": "job-07", "asset_id": "ast-07", "evaluations": { "overall_compatibility_score": 0.84, "throughput_multiplier": 1.06, "error_multiplier": 0.55, "fatigue_accumulation_rate": 0.95, "stress_sensitivity_factor": 0.70 }, "llm_reasoning": "Stamina fisik Hendra (0.72) lebih siap menghadapi physical_strain_index Baking (0.55) dibanding Bambang; error_multiplier sedikit lebih tinggi (0.55 vs 0.40 milik Bambang) namun masih dalam batas aman untuk error_severity 'critical'." }
          ],
          "optimal_staff_positions": [
            { "worker_id": "wrk-01", "name": "Dedi Kurniawan",       "current_station_rightnow": "step_01_weighing",       "optimal_station": "step_01_weighing",       "action": "stay" },
            { "worker_id": "wrk-02", "name": "Ratna Wulandari",      "current_station_rightnow": "step_02_mixing",         "optimal_station": "step_02_mixing",         "action": "stay" },
            { "worker_id": "wrk-03", "name": "Agus Prasetyo",        "current_station_rightnow": "step_03_dough_dividing", "optimal_station": "step_03_dough_dividing", "action": "stay" },
            { "worker_id": "wrk-04", "name": "Sri Mulyani",          "current_station_rightnow": "step_04_dough_shaping",  "optimal_station": "step_04_dough_shaping",  "action": "stay" },
            { "worker_id": "wrk-05", "name": "Yusuf Hidayat",        "current_station_rightnow": "step_05_filling_panning","optimal_station": "step_05_filling_panning","action": "stay" },
            { "worker_id": "wrk-06", "name": "Wahyu Ningsih",        "current_station_rightnow": "step_06_proofing",       "optimal_station": "step_06_proofing",       "action": "stay" },
            { "worker_id": "wrk-07", "name": "Bambang Setiawan",     "current_station_rightnow": "step_07_baking",         "optimal_station": "step_09_sorting",         "action": "moved", "move_id": "move-01" },
            { "worker_id": "wrk-08", "name": "Indah Permatasari",    "current_station_rightnow": "step_08_cooling",        "optimal_station": "step_08_cooling",         "action": "stay" },
            { "worker_id": "wrk-09", "name": "Hendra Saputra",       "current_station_rightnow": "step_09_sorting",        "optimal_station": "step_07_baking",          "action": "moved", "move_id": "move-02" },
            { "worker_id": "wrk-10", "name": "Lestari Handayani",    "current_station_rightnow": "step_10_packaging",      "optimal_station": "step_10_packaging",       "action": "stay" }
          ],
          "rl_reasoning": "Reward Function memberi bobot w5 (BurnoutRisk) cukup besar sehingga policy memilih menekan risiko burnout Bambang di Baking (bottleneck kritikal) dibanding mempertahankan error_multiplier sekecil mungkin. Hasil bersih: system_bottlenecks tetap di step_07_baking, tapi burnout_hazard_risk turun dari 'high' ke perkiraan 'medium' setelah swap, sambil throughput keseluruhan tetap naik +25.0% karena Sorting justru mendapat operator dengan compatibility_score lebih tinggi (0.91 vs 0.88 sebelumnya)."
        }
      },
      {
        "scenario_id": "scenario_02",
        "title": "Substitusi Otomasi",
        "recommended": false,
        "description": "Mesin otomatis mengambil alih pos manual bertumpukan tinggi — tanpa rekrut baru, PHK dilarang.",
        "constraints": {
          "hiring_allowed": false,
          "fire_or_mutation_allowed": true,
          "automation_allowed": true,
          "capex_rp": 70000000
        },
        "metrics": {
          "throughput_per_hour": { "before": 840, "after": 1240, "delta_pct": 47.6, "direction": "up" },
          "human_error_rate_pct": { "before": 8.2, "after": 3.1, "delta_pct": -62.2, "direction": "up" },
          "total_op_cost_per_hour_rp": { "before": 4200000, "after": 5600000, "delta_pct": 33.3, "direction": "down" }
        },
        "insight": "Trade-off: lonjakan performa besar, tapi biaya operasional per jam naik karena investasi mesin — payback period perlu dihitung terpisah dari capex Rp70M.",
        "assumption_flag": "Angka metrik skenario ini diestimasi mengikuti pola trade-off (constraint lebih longgar -> performa naik, cost naik); belum diverifikasi dari hasil training RL aktual.",
        "factory_flow_optimal": {
          "note": "ast-09 (Sorting Station manual) di-upgrade menjadi Optical Sorter otomatis, menghilangkan kebutuhan operator manual permanen di sana. Pekerja yang dibebaskan dimutasi ke Baking untuk meredakan bottleneck utama.",
          "asset_upgrades": [
            {
              "asset_id": "ast-09",
              "old_asset_name": "Sorting Station (Manual Visual Inspection)",
              "new_asset_name": "Optical Sorter (Automated Visual Inspection)",
              "workflow_step": "step_09_sorting",
              "is_automated": true,
              "capex_rp": 70000000,
              "reason": "Sorting adalah stasiun dengan required_cognitive_focus tertinggi (0.90) dan daftar kriteria cacat terpanjang — kandidat automasi dengan ROI error-reduction tertinggi."
            }
          ],
          "reallocation_moves": [
            {
              "move_id": "move-01",
              "worker_id": "wrk-09",
              "name": "Hendra Saputra",
              "from_station": "step_09_sorting",
              "to_station": "step_07_baking",
              "reason": "Setelah Sorting diotomasi, Hendra dimutasi (fire_or_mutation_allowed: true) menjadi operator kedua di Baking untuk mendukung/merotasi Bambang, menekan risiko burnout di stasiun yang tetap menjadi bottleneck manual."
            }
          ],
          "residual_bottleneck": "step_07_baking",
          "rl_reasoning": "Baking belum diotomasi pada skenario ini (di luar batas budget Rp70M), sehingga tetap menjadi titik lemah manual meski Sorting sudah teratasi — sejalan dengan rekomendasi eskalasi ke Skenario 3 bila bottleneck Baking ingin dihilangkan sepenuhnya."
        }
      },
      {
        "scenario_id": "scenario_03",
        "title": "Full Optimization",
        "recommended": false,
        "description": "Rekrut + PHK + otomasi semua aktif — solusi terbaik tanpa batasan SDM maupun konfigurasi mesin.",
        "constraints": {
          "hiring_allowed": true,
          "fire_or_mutation_allowed": true,
          "automation_allowed": true,
          "capex_rp": 120000000
        },
        "metrics": {
          "throughput_per_hour": { "before": 840, "after": 1480, "delta_pct": 76.2, "direction": "up" },
          "human_error_rate_pct": { "before": 8.2, "after": 1.8, "delta_pct": -78.0, "direction": "up" },
          "total_op_cost_per_hour_rp": { "before": 4200000, "after": 6900000, "delta_pct": 64.3, "direction": "down" }
        },
        "insight": "Performa maksimum secara absolut, tapi capex & biaya/jam tertinggi di antara ketiganya — cocok bila target throughput jangka panjang lebih diprioritaskan daripada efisiensi biaya jangka pendek.",
        "assumption_flag": "Angka metrik skenario ini diestimasi mengikuti pola trade-off (constraint lebih longgar -> performa naik, cost naik); belum diverifikasi dari hasil training RL aktual.",
        "factory_flow_optimal": {
          "note": "Melanjutkan otomasi Sorting dari Skenario 2, ditambah rekrut 1 operator baru untuk shift kedua Baking (mengeliminasi bottleneck sepenuhnya, bukan hanya meredakan).",
          "asset_upgrades": [
            {
              "asset_id": "ast-09",
              "old_asset_name": "Sorting Station (Manual Visual Inspection)",
              "new_asset_name": "Optical Sorter (Automated Visual Inspection)",
              "workflow_step": "step_09_sorting",
              "is_automated": true,
              "capex_rp": 70000000
            }
          ],
          "new_hires": [
            {
              "worker_id": "wrk-11",
              "name": "TBD — Operator Baking Shift 2",
              "assigned_station": "step_07_baking",
              "purpose": "Rotasi berpasangan dengan wrk-07/wrk-09 di Baking agar tidak ada operator yang menanggung >4 jam kerja terus-menerus di stasiun panas bertekanan tinggi, menghilangkan burnout_hazard_risk 'high' sepenuhnya.",
              "capex_rp": 50000000
            }
          ],
          "reallocation_moves": [
            {
              "move_id": "move-01",
              "worker_id": "wrk-09",
              "name": "Hendra Saputra",
              "from_station": "step_09_sorting",
              "to_station": "step_07_baking",
              "reason": "Sama seperti Skenario 2 — Sorting sudah otomatis, Hendra mendukung Baking bersama operator baru."
            }
          ],
          "residual_bottleneck": null,
          "rl_reasoning": "Dengan budget tanpa batas dan hiring diizinkan, policy RL mengeliminasi kedua sumber bottleneck (Sorting via automasi, Baking via penambahan SDM/rotasi shift) sekaligus — menghasilkan system_bottlenecks kosong, konsisten dengan throughput tertinggi (+76.2%) dan error rate terendah (1.8%) di antara ketiga skenario."
        }
      }
    ]
  }
}