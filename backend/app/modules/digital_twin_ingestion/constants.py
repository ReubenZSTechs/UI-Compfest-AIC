# app/modules/digital_twin_ingestion/constants.py
"""
Data mentah digital twin (Sweet Bread, PT XYZ Yogyakarta).
Modul ini stateless: tidak ada tabel, tidak ada DB call — persis pola
modul `simulation`. Kalau nanti pipeline ingestion (agent) sudah siap
menulis data dinamis, baru modul ini disambungkan ke tabel/DB.
"""

import json

DIGITAL_TWIN_DATA = {
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
            "step_10_packaging",
        ],
    },
    "assets": [
        {
            "asset_id": "ast-01",
            "asset_name": "Digital Weighing Scale",
            "category": "measuring_equipment",
            "workflow_step": "step_01_weighing",
            "is_automated": True,
            "base_throughput_capacity": 300,
            "operational_cost_per_hour": 4.0,
            "environmental_factors": {
                "noise_level_db": 45,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.15,
            },
            "metric_derivation_reasoning": "Timbangan digital tidak menghasilkan getaran/kebisingan signifikan. Beban fisik rendah karena operator hanya menakar dan memasukkan bahan sesuai formulasi. Nilai numerik (kapasitas, biaya) diestimasi, tidak tercantum di tabel sumber.",
        },
        {
            "asset_id": "ast-02",
            "asset_name": "Mixer",
            "category": "machine",
            "workflow_step": "step_02_mixing",
            "is_automated": True,
            "base_throughput_capacity": 150,
            "operational_cost_per_hour": 10.0,
            "environmental_factors": {
                "noise_level_db": 72,
                "vibration_hazard_level": "medium",
                "physical_strain_index": 0.4,
            },
            "metric_derivation_reasoning": "Mixer menghasilkan kebisingan & getaran menengah selama proses pengadukan adonan. QC pada tahap ini ketat (homogenitas, elastisitas adonan), sehingga fokus kognitif operator dinilai tinggi di job_desks.",
        },
        {
            "asset_id": "ast-03",
            "asset_name": "Dough Divider",
            "category": "machine",
            "workflow_step": "step_03_dough_dividing",
            "is_automated": True,
            "base_throughput_capacity": 200,
            "operational_cost_per_hour": 9.0,
            "environmental_factors": {
                "noise_level_db": 68,
                "vibration_hazard_level": "medium",
                "physical_strain_index": 0.3,
            },
            "metric_derivation_reasoning": "Mesin pembagi adonan otomatis dengan getaran mekanis sedang. Operator hanya mengoperasikan dan memantau, tanpa QC checklist eksplisit di tabel sumber.",
        },
        {
            "asset_id": "ast-04",
            "asset_name": "Rounder Machine / Dough Sheeter",
            "category": "machine",
            "workflow_step": "step_04_dough_shaping",
            "is_automated": True,
            "base_throughput_capacity": 200,
            "operational_cost_per_hour": 9.0,
            "environmental_factors": {
                "noise_level_db": 66,
                "vibration_hazard_level": "medium",
                "physical_strain_index": 0.3,
            },
            "metric_derivation_reasoning": "Mesin pembentuk adonan (rounder/sheeter) otomatis. Tidak ada QC eksplisit di tabel; peran operator terbatas pada pengawasan proses.",
        },
        {
            "asset_id": "ast-05",
            "asset_name": "Breadline Machine",
            "category": "conveyor_automation",
            "workflow_step": "step_05_filling_panning",
            "is_automated": True,
            "base_throughput_capacity": 180,
            "operational_cost_per_hour": 11.0,
            "environmental_factors": {
                "noise_level_db": 64,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.35,
            },
            "metric_derivation_reasoning": "Breadline machine menata adonan ke baking tin. QC ketat pada jarak antar adonan (±4 cm) menuntut ketelitian visual operator meski beban fisik moderat.",
        },
        {
            "asset_id": "ast-06",
            "asset_name": "Proofing Cabinet",
            "category": "environmental_chamber",
            "workflow_step": "step_06_proofing",
            "is_automated": True,
            "base_throughput_capacity": 250,
            "operational_cost_per_hour": 7.0,
            "environmental_factors": {
                "noise_level_db": 40,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.1,
            },
            "metric_derivation_reasoning": "Proofing cabinet adalah ruang terkendali suhu/kelembapan; beban fisik operator rendah, namun QC menuntut presisi suhu 55-60°C selama 50-60 menit dan pemantauan volume roti.",
        },
        {
            "asset_id": "ast-07",
            "asset_name": "Deck Oven / Combi Oven",
            "category": "machine",
            "workflow_step": "step_07_baking",
            "is_automated": True,
            "base_throughput_capacity": 220,
            "operational_cost_per_hour": 18.0,
            "environmental_factors": {
                "noise_level_db": 58,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.55,
            },
            "metric_derivation_reasoning": "Oven menghasilkan panas tinggi (bahaya panas, bukan kebisingan) sehingga physical_strain_index dinaikkan. QC kritikal: suhu 170°C selama 8-10 menit, kematangan & warna roti harus presisi agar tidak gosong.",
        },
        {
            "asset_id": "ast-08",
            "asset_name": "Cooling Area",
            "category": "manual_station",
            "workflow_step": "step_08_cooling",
            "is_automated": False,
            "base_throughput_capacity": 220,
            "operational_cost_per_hour": 2.0,
            "environmental_factors": {
                "noise_level_db": 35,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.25,
            },
            "metric_derivation_reasoning": "Tidak ada peralatan (tabel: '—'); area pendinginan bersifat pasif. Beban fisik berasal dari aktivitas memindahkan loyang/produk secara manual.",
        },
        {
            "asset_id": "ast-09",
            "asset_name": "Sorting Station (Manual Visual Inspection)",
            "category": "manual_station",
            "workflow_step": "step_09_sorting",
            "is_automated": False,
            "base_throughput_capacity": 200,
            "operational_cost_per_hour": 5.0,
            "environmental_factors": {
                "noise_level_db": 40,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.2,
            },
            "metric_derivation_reasoning": "Tidak ada peralatan tercantum ('—'); sortir sepenuhnya manual berbasis inspeksi visual. Beban kognitif tinggi karena daftar cacat yang harus dideteksi cukup panjang (gosong, filling bocor, lengket, hancur, kurang matang, dll.).",
        },
        {
            "asset_id": "ast-10",
            "asset_name": "Packaging Machine",
            "category": "machine",
            "workflow_step": "step_10_packaging",
            "is_automated": False,
            "base_throughput_capacity": 200,
            "operational_cost_per_hour": 8.0,
            "environmental_factors": {
                "noise_level_db": 60,
                "vibration_hazard_level": "low",
                "physical_strain_index": 0.3,
            },
            "metric_derivation_reasoning": "Meski disebut 'Packaging Machine', kolom Otomatisasi bertanda '—' pada tabel sumber, artinya mesin dioperasikan/dijalankan manual oleh operator, bukan berjalan otomatis penuh.",
        },
    ],
    "job_desks": [
        {
            "job_id": "job-01",
            "job_title": "Operator Weighing",
            "workflow_step": "step_01_weighing",
            "assigned_asset_id": "ast-01",
            "demands": {
                "required_cognitive_focus": 0.55,
                "physical_demand_level": "low",
                "task_complexity": 0.3,
                "error_severity": "moderate",
            },
            "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
            "metric_derivation_reasoning": "Tugas menimbang bahan sesuai formulasi bersifat rutin dan terstandar, fokus kognitif sedang (ketepatan takaran) dengan beban fisik rendah.",
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
                "error_severity": "high",
            },
            "qc_requirement": "Memastikan adonan homogen, elastis, dan tidak lengket.",
            "metric_derivation_reasoning": "QC eksplisit di tabel (homogenitas, elastisitas adonan) menuntut fokus kognitif dan judgement lebih tinggi dibanding tahap penimbangan.",
        },
        {
            "job_id": "job-03",
            "job_title": "Operator Dough Dividing",
            "workflow_step": "step_03_dough_dividing",
            "assigned_asset_id": "ast-03",
            "demands": {
                "required_cognitive_focus": 0.5,
                "physical_demand_level": "medium",
                "task_complexity": 0.35,
                "error_severity": "moderate",
            },
            "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
            "metric_derivation_reasoning": "Peran operator terbatas pada mengoperasikan dan memantau mesin pembagi adonan; tidak ada kriteria QC tertulis di tabel.",
        },
        {
            "job_id": "job-04",
            "job_title": "Operator Dough Shaping",
            "workflow_step": "step_04_dough_shaping",
            "assigned_asset_id": "ast-04",
            "demands": {
                "required_cognitive_focus": 0.5,
                "physical_demand_level": "medium",
                "task_complexity": 0.35,
                "error_severity": "moderate",
            },
            "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
            "metric_derivation_reasoning": "Sama seperti dough dividing, operator hanya mengoperasikan dan memantau proses rounder/sheeter.",
        },
        {
            "job_id": "job-05",
            "job_title": "Operator Filling & Panning",
            "workflow_step": "step_05_filling_panning",
            "assigned_asset_id": "ast-05",
            "demands": {
                "required_cognitive_focus": 0.7,
                "physical_demand_level": "medium",
                "task_complexity": 0.45,
                "error_severity": "moderate",
            },
            "qc_requirement": "Memastikan jarak antar adonan ±4 cm.",
            "metric_derivation_reasoning": "QC presisi jarak (±4 cm) menuntut ketelitian visual yang konsisten selama proses penataan pada baking tin berjalan.",
        },
        {
            "job_id": "job-06",
            "job_title": "Operator Proofing",
            "workflow_step": "step_06_proofing",
            "assigned_asset_id": "ast-06",
            "demands": {
                "required_cognitive_focus": 0.6,
                "physical_demand_level": "low",
                "task_complexity": 0.4,
                "error_severity": "high",
            },
            "qc_requirement": "Memastikan suhu 55-60°C selama 50-60 menit serta adonan mengembang dengan baik (volume roti).",
            "metric_derivation_reasoning": "Kesalahan pengaturan suhu/waktu proofing berdampak langsung pada kualitas volume roti pada tahap berikutnya (baking), sehingga error_severity dinilai tinggi walau beban fisik rendah.",
        },
        {
            "job_id": "job-07",
            "job_title": "Operator Baking",
            "workflow_step": "step_07_baking",
            "assigned_asset_id": "ast-07",
            "demands": {
                "required_cognitive_focus": 0.85,
                "physical_demand_level": "high",
                "task_complexity": 0.7,
                "error_severity": "critical",
            },
            "qc_requirement": "Memastikan suhu 170°C selama 8-10 menit sehingga kematangan roti sesuai dan tidak gosong (warna roti).",
            "metric_derivation_reasoning": "Tahap paling kritikal: parameter suhu/waktu presisi, risiko panas tinggi (beban fisik), dan kesalahan berakibat langsung pada kegagalan produk (gosong).",
        },
        {
            "job_id": "job-08",
            "job_title": "Operator Cooling",
            "workflow_step": "step_08_cooling",
            "assigned_asset_id": "ast-08",
            "demands": {
                "required_cognitive_focus": 0.3,
                "physical_demand_level": "medium",
                "task_complexity": 0.2,
                "error_severity": "low",
            },
            "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
            "metric_derivation_reasoning": "Tugas manual memindahkan produk ke area pendinginan; beban fisik dari mengangkat/memindahkan, fokus kognitif rendah.",
        },
        {
            "job_id": "job-09",
            "job_title": "Inspektur Sortir",
            "workflow_step": "step_09_sorting",
            "assigned_asset_id": "ast-09",
            "demands": {
                "required_cognitive_focus": 0.9,
                "physical_demand_level": "low",
                "task_complexity": 0.5,
                "error_severity": "high",
            },
            "qc_requirement": "Memeriksa produk cacat: gosong, filling bocor, lengket, hancur, kurang matang, tidak mengembang, tanpa topping, ukuran tidak sesuai, dan cacat lainnya.",
            "metric_derivation_reasoning": "Daftar kriteria cacat yang panjang dan beragam menuntut fokus kognitif sangat tinggi meski beban fisik rendah; ini adalah gerbang QC akhir sebelum packaging.",
        },
        {
            "job_id": "job-10",
            "job_title": "Operator Packaging",
            "workflow_step": "step_10_packaging",
            "assigned_asset_id": "ast-10",
            "demands": {
                "required_cognitive_focus": 0.4,
                "physical_demand_level": "medium",
                "task_complexity": 0.25,
                "error_severity": "low",
            },
            "qc_requirement": "Tidak ada QC eksplisit pada tabel sumber untuk tahap ini.",
            "metric_derivation_reasoning": "Tugas rutin mengemas produk yang sudah lolos sorting; risiko kesalahan relatif rendah karena QC utama sudah dilakukan di tahap sebelumnya.",
        },
    ],
    "workers": [
        {
            "worker_id": "wrk-01",
            "name": "Dedi Kurniawan",
            "demographics": {
                "age": 35,
                "gender": "male",
                "years_of_experience": 8,
                "baseline_physical_stamina": 0.75,
                "cognitive_resilience": 0.7,
            },
            "shift_context": {"hours_worked_today": 3.0, "consecutive_shifts": 2},
        },
        {
            "worker_id": "wrk-02",
            "name": "Ratna Wulandari",
            "demographics": {
                "age": 29,
                "gender": "female",
                "years_of_experience": 5,
                "baseline_physical_stamina": 0.8,
                "cognitive_resilience": 0.82,
            },
            "shift_context": {"hours_worked_today": 3.0, "consecutive_shifts": 3},
        },
        {
            "worker_id": "wrk-03",
            "name": "Agus Prasetyo",
            "demographics": {
                "age": 41,
                "gender": "male",
                "years_of_experience": 12,
                "baseline_physical_stamina": 0.68,
                "cognitive_resilience": 0.75,
            },
            "shift_context": {"hours_worked_today": 4.0, "consecutive_shifts": 4},
        },
        {
            "worker_id": "wrk-04",
            "name": "Sri Mulyani",
            "demographics": {
                "age": 26,
                "gender": "female",
                "years_of_experience": 3,
                "baseline_physical_stamina": 0.85,
                "cognitive_resilience": 0.72,
            },
            "shift_context": {"hours_worked_today": 4.0, "consecutive_shifts": 2},
        },
        {
            "worker_id": "wrk-05",
            "name": "Yusuf Hidayat",
            "demographics": {
                "age": 33,
                "gender": "male",
                "years_of_experience": 7,
                "baseline_physical_stamina": 0.78,
                "cognitive_resilience": 0.78,
            },
            "shift_context": {"hours_worked_today": 2.5, "consecutive_shifts": 1},
        },
        {
            "worker_id": "wrk-06",
            "name": "Wahyu Ningsih",
            "demographics": {
                "age": 30,
                "gender": "female",
                "years_of_experience": 6,
                "baseline_physical_stamina": 0.7,
                "cognitive_resilience": 0.8,
            },
            "shift_context": {"hours_worked_today": 2.5, "consecutive_shifts": 3},
        },
        {
            "worker_id": "wrk-07",
            "name": "Bambang Setiawan",
            "demographics": {
                "age": 45,
                "gender": "male",
                "years_of_experience": 18,
                "baseline_physical_stamina": 0.65,
                "cognitive_resilience": 0.9,
            },
            "shift_context": {"hours_worked_today": 5.0, "consecutive_shifts": 5},
        },
        {
            "worker_id": "wrk-08",
            "name": "Indah Permatasari",
            "demographics": {
                "age": 24,
                "gender": "female",
                "years_of_experience": 2,
                "baseline_physical_stamina": 0.88,
                "cognitive_resilience": 0.6,
            },
            "shift_context": {"hours_worked_today": 1.5, "consecutive_shifts": 1},
        },
        {
            "worker_id": "wrk-09",
            "name": "Hendra Saputra",
            "demographics": {
                "age": 38,
                "gender": "male",
                "years_of_experience": 10,
                "baseline_physical_stamina": 0.72,
                "cognitive_resilience": 0.85,
            },
            "shift_context": {"hours_worked_today": 4.5, "consecutive_shifts": 4},
        },
        {
            "worker_id": "wrk-10",
            "name": "Lestari Handayani",
            "demographics": {
                "age": 27,
                "gender": "female",
                "years_of_experience": 4,
                "baseline_physical_stamina": 0.83,
                "cognitive_resilience": 0.68,
            },
            "shift_context": {"hours_worked_today": 1.5, "consecutive_shifts": 2},
        },
    ],
    "factory_flow_rightnow": {
        "snapshot_timestamp": "2026-07-27T09:30:00+07:00",
        "note": "Snapshot kondisi lantai produksi saat ini: posisi tiap staf, tahap yang sedang dikerjakan, dan tujuan perpindahan (hand-off) ke tahap berikutnya dalam alur linear step_01 -> step_10.",
        "staff_current_positions": [
            {
                "worker_id": "wrk-01",
                "name": "Dedi Kurniawan",
                "current_station": "step_01_weighing",
                "current_asset_id": "ast-01",
                "activity_status": "processing",
                "moving_to_next_step": "step_02_mixing",
                "handoff_item": "batch adonan tertimbang #B-241",
            },
            {
                "worker_id": "wrk-02",
                "name": "Ratna Wulandari",
                "current_station": "step_02_mixing",
                "current_asset_id": "ast-02",
                "activity_status": "processing",
                "moving_to_next_step": "step_03_dough_dividing",
                "handoff_item": "adonan tercampur #B-240",
            },
            {
                "worker_id": "wrk-03",
                "name": "Agus Prasetyo",
                "current_station": "step_03_dough_dividing",
                "current_asset_id": "ast-03",
                "activity_status": "processing",
                "moving_to_next_step": "step_04_dough_shaping",
                "handoff_item": "potongan adonan #B-239",
            },
            {
                "worker_id": "wrk-04",
                "name": "Sri Mulyani",
                "current_station": "step_04_dough_shaping",
                "current_asset_id": "ast-04",
                "activity_status": "processing",
                "moving_to_next_step": "step_05_filling_panning",
                "handoff_item": "adonan terbentuk #B-238",
            },
            {
                "worker_id": "wrk-05",
                "name": "Yusuf Hidayat",
                "current_station": "step_05_filling_panning",
                "current_asset_id": "ast-05",
                "activity_status": "processing",
                "moving_to_next_step": "step_06_proofing",
                "handoff_item": "loyang terisi #B-237",
            },
            {
                "worker_id": "wrk-06",
                "name": "Wahyu Ningsih",
                "current_station": "step_06_proofing",
                "current_asset_id": "ast-06",
                "activity_status": "waiting_on_machine",
                "moving_to_next_step": "step_07_baking",
                "handoff_item": "loyang proofing #B-236 (25 menit tersisa)",
            },
            {
                "worker_id": "wrk-07",
                "name": "Bambang Setiawan",
                "current_station": "step_07_baking",
                "current_asset_id": "ast-07",
                "activity_status": "processing",
                "moving_to_next_step": "step_08_cooling",
                "handoff_item": "loyang panggang #B-235",
            },
            {
                "worker_id": "wrk-08",
                "name": "Indah Permatasari",
                "current_station": "step_08_cooling",
                "current_asset_id": "ast-08",
                "activity_status": "idle_waiting_input",
                "moving_to_next_step": "step_09_sorting",
                "handoff_item": "produk mendingin #B-234",
            },
            {
                "worker_id": "wrk-09",
                "name": "Hendra Saputra",
                "current_station": "step_09_sorting",
                "current_asset_id": "ast-09",
                "activity_status": "processing",
                "moving_to_next_step": "step_10_packaging",
                "handoff_item": "produk lolos sortir #B-233",
            },
            {
                "worker_id": "wrk-10",
                "name": "Lestari Handayani",
                "current_station": "step_10_packaging",
                "current_asset_id": "ast-10",
                "activity_status": "processing",
                "moving_to_next_step": "finished_goods_storage",
                "handoff_item": "produk terkemas #B-232",
            },
        ],
    },
}


def generate_full_compatibility_matrix(data):
    workers = data["workers"]
    jobs = data["job_desks"]
    assets = {a["asset_id"]: a for a in data["assets"]}

    phys_map = {"low": 0.2, "medium": 0.5, "high": 0.8}
    sev_map = {"low": 0.2, "moderate": 0.5, "high": 0.8, "critical": 1.0}

    full_matrix = []

    for w in workers:
        w_id = w["worker_id"]
        w_name = w["name"]
        stamina = w["demographics"]["baseline_physical_stamina"]
        cog = w["demographics"]["cognitive_resilience"]
        exp = w["demographics"]["years_of_experience"]
        hrs = w["shift_context"]["hours_worked_today"]
        shifts = w["shift_context"]["consecutive_shifts"]

        for j in jobs:
            j_id = j["job_id"]
            j_title = j["job_title"]
            a_id = j["assigned_asset_id"]
            asset = assets[a_id]

            req_cog = j["demands"]["required_cognitive_focus"]
            phys_req = phys_map[j["demands"]["physical_demand_level"]]
            severity = sev_map[j["demands"]["error_severity"]]
            strain = asset["environmental_factors"]["physical_strain_index"]

            # 1. Overall Compatibility Score
            cog_match = 1.0 - abs(cog - req_cog) * 0.4
            phys_match = 1.0 - max(0, phys_req - stamina) * 0.6
            exp_match = min(1.0, 0.5 + (exp / 15.0) * 0.5)

            overall_score = round(
                min(
                    0.98,
                    max(
                        0.35,
                        cog_match * 0.4 + phys_match * 0.35 + exp_match * 0.25,
                    ),
                ),
                2,
            )

            # 2. Throughput Multiplier
            throughput = round(
                min(
                    1.25,
                    max(
                        0.70,
                        0.85 + (exp / 20.0) * 0.25 + (stamina - phys_req) * 0.15,
                    ),
                ),
                2,
            )

            # 3. Error Multiplier
            error_mult = round(
                max(
                    0.35,
                    min(
                        1.50,
                        1.25
                        - (cog * 0.4)
                        - (exp / 20.0) * 0.3
                        + (severity * 0.2),
                    ),
                ),
                2,
            )

            # 4. Fatigue Accumulation Rate
            fatigue_rate = round(
                max(
                    0.30,
                    min(
                        1.60,
                        0.35
                        + (phys_req + strain) * 0.4
                        + (hrs / 8.0) * 0.3
                        + (shifts / 5.0) * 0.25
                        - (stamina * 0.3),
                    ),
                ),
                2,
            )

            # 5. Stress Sensitivity Factor
            stress_factor = round(
                max(
                    0.40,
                    min(
                        0.95,
                        0.85
                        - (cog * 0.3)
                        + (severity * 0.25)
                        - (exp / 30.0),
                    ),
                ),
                2,
            )

            # Dynamic LLM Reasoning
            cog_eval = "memadai" if cog >= req_cog else "kurang seimbang"
            phys_eval = (
                "tercover baik"
                if stamina >= phys_req
                else "berpotensi memicu kelelahan cepat"
            )

            reasoning = (
                f"{w_name} ({exp} thn exp, stamina {stamina}, resiliensi {cog}) dievaluasi pada {j_title}. "
                f"Kapasitas kognitif {cog_eval} untuk tuntutan tugas ({req_cog}), "
                f"sedangkan beban fisik {phys_eval}. "
                f"Kondisi shift ({hrs} jam kerja, {shifts} shift beruntun) mempengaruhi laju kelelahan ({fatigue_rate}x)."
            )

            full_matrix.append({
                "worker_id": w_id,
                "job_id": j_id,
                "asset_id": a_id,
                "evaluations": {
                    "overall_compatibility_score": overall_score,
                    "throughput_multiplier": throughput,
                    "error_multiplier": error_mult,
                    "fatigue_accumulation_rate": fatigue_rate,
                    "stress_sensitivity_factor": stress_factor,
                },
                "llm_reasoning": reasoning,
            })

    return full_matrix


# Perbarui struktur data utama secara dinamis
DIGITAL_TWIN_DATA["llm_compatibility_and_evaluations"] = (
    generate_full_compatibility_matrix(DIGITAL_TWIN_DATA)
)