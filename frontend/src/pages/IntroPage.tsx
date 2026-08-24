// frontend/src/pages/IntroPage.tsx
// Halaman 1: Introduction — pengenalan aplikasi, panduan singkat,
// pilihan template canvas, dan CTA "Mulai Desain Canvas".
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ROUTES } from "@/app/router/routes";
import {
  CANVAS_TEMPLATES,
  TEMPLATE_META,
} from "@/features/canvas/templates/templates";
import type { CanvasTemplateId } from "@/features/canvas/types/canvas.types";
import { useDraftStore } from "@/store/draftStore";
import styles from "./IntroPage.module.css";

const TEMPLATE_IDS: CanvasTemplateId[] = ["blank", "serial", "parallel"];

const GUIDE_STEPS = [
  {
    title: "1 · Gambar Alur Kerja",
    description:
      "Klik toolbar 'Tambah Proses' lalu klik kanvas untuk menaruh stasiun kerja. Susun secara seri atau paralel.",
  },
  {
    title: "2 · Tambahkan Pekerja",
    description:
      "Tambah node pekerja, lalu tarik garis ASSIGNED_TO dari pekerja menuju proses yang dikerjakan.",
  },
  {
    title: "3 · Hubungkan Relasi",
    description:
      "Hubungkan proses ke proses dengan garis FLOW untuk menunjukkan alur produksi.",
  },
  {
    title: "4 · Analisis AI",
    description:
      "Saat layout sudah yakin, tekan 'Mulai Analisis AI'. Canvas mengirim JSON bersih & menampilkan status verifikasi.",
  },
];

export function IntroPage() {
  const navigate = useNavigate();
  const [selectedTemplate, setSelectedTemplate] = useState<CanvasTemplateId>("serial");

  function startCanvas() {
    const ds = useDraftStore.getState();
    const existing = ds.drafts.find(
      (d) =>
        d.templateId === selectedTemplate &&
        d.canvasData.nodes.length <= 4 &&
        Date.now() - new Date(d.createdAt).getTime() < 60_000
    );
    if (existing) {
      ds.loadDraft(existing.projectId);
      navigate(`${ROUTES.LIVE}?projectId=${existing.projectId}`);
      return;
    }
    const projectId = ds.createDraft(selectedTemplate);
    navigate(`${ROUTES.LIVE}?projectId=${projectId}`);
  }

  return (
    <div className={styles.page}>
      {/* Hero */}
<section className={styles.hero}>
        <span className={styles.eyebrow}>Smart Manufacturing · Interactive Canvas Workspace</span>
        <h1 className={styles.title}>
          Desain Alur Pabrikmu, <span className={styles.accent}>Lalu Biarkan AI Bekerja</span>
        </h1>
        <p className={styles.subtitle}>
          Dari form statis ke papan desain bebas (mirip Miro). Susun proses, tugaskan pekerja,
          tarik garis relasi — tanpa API call. Eksekusi AI hanya terjadi saat kamu menekan
          <strong> "Mulai Analisis AI"</strong>, dengan payload JSON yang bersih dari data visual.
        </p>
        
        {/* Tombol Aksi */}
        <div className={styles.heroActions}>
          <button type="button" className={styles.cta} onClick={startCanvas}>
            Mulai Desain Canvas →
          </button>
          <Link 
            to={ROUTES.DASHBOARD ?? "/dashboard"} 
            className={styles.dashboardBtn}
          >
            Lihat Saved Drafts / Dashboard
          </Link>
        </div>
      </section>

      {/* Template picker */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Pilih Template Awal</h2>
        <div className={styles.templateGrid}>
          {TEMPLATE_IDS.map((id) => {
            const meta = TEMPLATE_META[id];
            const counts = CANVAS_TEMPLATES[id]();
            const processCount = counts.nodes.filter((n) => n.data.kind === "process").length;
            const workerCount = counts.nodes.length - processCount;
            const edgeCount = counts.edges.length;

            return (
              <button
                key={id}
                type="button"
                className={`${styles.templateCard} ${
                  selectedTemplate === id ? styles.templateActive : ""
                }`}
                onClick={() => setSelectedTemplate(id)}
                aria-pressed={selectedTemplate === id}
              >
                <span className={styles.templateBadge}>{edgeCount} relasi</span>
                <h3 className={styles.templateTitle}>{meta.title}</h3>
                <p className={styles.templateDesc}>{meta.description}</p>
                <div className={styles.templatePreview} aria-hidden="true">
                  {id === "blank" && <span className={styles.previewBlank}>Kanvas kosong</span>}
                  {id === "serial" && (
                    <div className={styles.previewRow}>
                      {Array.from({ length: processCount }).map((_, i) => (
                        <span key={i} className={styles.previewProcess} />
                      ))}
                      {Array.from({ length: workerCount }).map((_, i) => (
                        <span key={`w-${i}`} className={styles.previewWorker} />
                      ))}
                    </div>
                  )}
                  {id === "parallel" && (
                    <div className={styles.previewParallel}>
                      <span className={styles.previewProcess} />
                      <div className={styles.previewFork}>
                        <span className={styles.previewProcess} />
                        <span className={styles.previewProcess} />
                      </div>
                      <span className={styles.previewProcess} />
                    </div>
                  )}
                </div>
                <span className={styles.templateMeta}>
                  {processCount} proses · {workerCount} pekerja
                </span>
              </button>
            );
          })}
        </div>
        <button type="button" className={styles.secondaryCta} onClick={startCanvas}>
          Mulai dengan Template Terpilih →
        </button>
      </section>

      {/* Panduan singkat */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Cara Kerja dalam 4 Langkah</h2>
        <div className={styles.guideGrid}>
          {GUIDE_STEPS.map((step) => (
            <div key={step.title} className={styles.guideCard}>
              <h3 className={styles.guideTitle}>{step.title}</h3>
              <p className={styles.guideDesc}>{step.description}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default IntroPage;