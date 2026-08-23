// frontend/src/pages/LandingPage.tsx
// Landing page utama Pabrikers: Portal pengenalan platform sebelum masuk ke /intro.
// Menampilkan arsitektur platform, keunggulan kanvas interaktif, engine AI/RL,
// simulasi ROI interaktif, alur 4 langkah kerja, dan CTA ke workspace.
import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./LandingPage.module.css";

interface FAQItem {
  q: string;
  a: string;
}

const FAQS: FAQItem[] = [
  {
    q: "Apakah koordinat visual dan zoom kanvas dikirim ke model AI?",
    a: "Tidak. Arsitektur kami memisahkan secara ketat antara Visual State (koordinat X/Y, zoom, drag-and-drop) dan Clean Graph Payload. AI hanya menerima topologi relasi murni (FLOW dan ASSIGNED_TO) tanpa beban metadata visual, menjamin efisiensi token dan akurasi analisis.",
  },
  {
    q: "Bagaimana AI menghasilkan 3 skenario optimasi yang berbeda?",
    a: "Engine Reinforcement Learning kami menjalankan simulasi hingga 10.000 episode dengan reward function multi-objektif (memaksimalkan throughput, meminimalkan biaya operasional, dan menekan fatigue pekerja). Hasilnya dikelompokkan ke dalam 3 trade-off: Realokasi SDM Murni, Substitusi Otomasi Robotik, dan Full Capacity Expansion.",
  },
  {
    q: "Bagaimana cara kerja fitur What-If Simulator di AI Chatbot?",
    a: "Pengguna dapat mengajukan skenario hipotetis melalui chatbot (misalnya: pemotongan budget 30%, pengurangan operator, atau lonjakan demand 20%). AI langsung mengalkulasi ulang variansi metrik dan memberikan saran mitigasi bottleneck secara real-time.",
  },
  {
    q: "Apakah proyek saya tersimpan otomatis saat berpindah halaman?",
    a: "Ya. Konsep Unified ProjectDraft kami bertindak sebagai single source of truth yang otomatis menyinkronkan kanvas, riwayat percakapan asisten, kebijakan operasional, dan hasil analitik ke penyimpanan lokal dan backup server.",
  },
];

export function LandingPage() {
  const navigate = useNavigate();

  // State untuk ROI Calculator Mini-Widget
  const [operatorCount, setOperatorCount] = useState<number>(24);
  const [currentThroughput, setCurrentThroughput] = useState<number>(850);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  // Perhitungan ROI Dinamis
  const roiCalculations = useMemo(() => {
    const potentialThroughputGain = Math.round(currentThroughput * 0.42);
    const newThroughput = currentThroughput + potentialThroughputGain;
    const monthlySavingEstimate = Math.round(operatorCount * 1_250_000 * 0.18);
    const formattedSaving = new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(monthlySavingEstimate);

    return {
      potentialGainPercent: "+42.8%",
      newThroughput: newThroughput.toLocaleString("id-ID"),
      monthlySaving: formattedSaving,
      paybackPeriod: "2.5 Bulan",
    };
  }, [operatorCount, currentThroughput]);

  function toggleFaq(idx: number) {
    setOpenFaqIndex((prev) => (prev === idx ? null : idx));
  }

  return (
    <div className={styles.landingContainer}>
      {/* 1. TOP NAVIGATION BAR */}
      <header className={styles.navbar}>
        <div className={styles.navInner}>
          <Link to="/" className={styles.navBrand}>
            <div className={styles.brandLogoBox}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.4">
                <path d="M3 3v18h18" />
                <path d="m19 9-5 5-4-4-3 3" />
              </svg>
            </div>
            <div className={styles.brandTitleCol}>
              <span className={styles.brandName}>Pabrikers</span>
              <span className={styles.brandTagline}>Smart Factory Platform</span>
            </div>
          </Link>

          <nav className={styles.navLinks}>
            <a href="#fitur" className={styles.navLink}>Fitur</a>
            <a href="#alur-kerja" className={styles.navLink}>Alur Kerja</a>
            <a href="#kalkulator" className={styles.navLink}>Simulasi ROI</a>
            <a href="#faq" className={styles.navLink}>FAQ</a>
          </nav>

          <div className={styles.navActions}>
            <Link to="/dashboard" className={styles.secondaryBtn}>
              Dashboard
            </Link>
            <button
              type="button"
              className={styles.primaryCtaBtn}
              onClick={() => navigate("/intro")}
            >
              <span>Mulai Desain Canvas</span>
              <span className={styles.btnArrow}>→</span>
            </button>
          </div>
        </div>
      </header>

      {/* 2. HERO SECTION */}
      <section className={styles.heroSection}>
        <div className={styles.heroBackgroundPattern} aria-hidden="true" />
        <div className={styles.heroContent}>
          <div className={styles.heroBadge}>
            <span className={styles.pulseDot} />
            <span>AI-POWERED MANUFACTURING ORCHESTRATION</span>
          </div>

          <h1 className={styles.heroTitle}>
            Desain Alur Produksi Pabrik, <br />
            <span className={styles.heroHighlight}>Optimalkan dengan AI Reinforcement Learning</span>
          </h1>

          <p className={styles.heroDescription}>
            Tinggalkan *trial-and-error* berbiaya mahal di lini fisik. Susun stasiun proses dan alokasi operator
            di kanvas interaktif bebas, biarkan AI mensimulasikan jutaan skenario, dan pantau efisiensi digital twin
            secara presisi tinggi.
          </p>

          <div className={styles.heroCtaGroup}>
            <button
              type="button"
              className={styles.heroPrimaryBtn}
              onClick={() => navigate("/intro")}
            >
              <span>Mulai Desain Sekarang</span>
              <span className={styles.heroBtnArrow}>→</span>
            </button>
            <button
              type="button"
              className={styles.heroSecondaryBtn}
              onClick={() => navigate("/rec_1")}
            >
              <span>Lihat Contoh Analytics Report</span>
            </button>
          </div>

          {/* Key Metrik Strip */}
          <div className={styles.heroMetricsStrip}>
            <div className={styles.heroMetricItem}>
              <span className={styles.metricVal}>+78.6%</span>
              <span className={styles.metricLabel}>Max Throughput Gain</span>
            </div>
            <div className={styles.heroMetricDivider} />
            <div className={styles.heroMetricItem}>
              <span className={styles.metricVal}>-89.0%</span>
              <span className={styles.metricLabel}>Human Error Reduction</span>
            </div>
            <div className={styles.heroMetricDivider} />
            <div className={styles.heroMetricItem}>
              <span className={styles.metricVal}>10,000+</span>
              <span className={styles.metricLabel}>RL Episodes Simulated</span>
            </div>
            <div className={styles.heroMetricDivider} />
            <div className={styles.heroMetricItem}>
              <span className={styles.metricVal}>&lt; 3 Detik</span>
              <span className={styles.metricLabel}>Graph Verification Time</span>
            </div>
          </div>
        </div>

        {/* 3. INTERACTIVE PRODUCT PREVIEW CARD */}
        <div className={styles.heroMockupWrapper}>
          <div className={styles.mockupHeader}>
            <div className={styles.mockupDots}>
              <span className={styles.mockDotRed} />
              <span className={styles.mockDotYellow} />
              <span className={styles.mockDotGreen} />
            </div>
            <div className={styles.mockupTitleBar}>
              <span>Interactive Workspace · Canvas Live Mode (Single SOT)</span>
            </div>
            <div className={styles.mockupLiveBadge}>LIVE SIMULATION</div>
          </div>

          <div className={styles.mockupCanvasView}>
            {/* Visual Canvas Nodes Flow Simulation */}
            <div className={styles.flowNodeCard}>
              <div className={styles.nodeKindBadge}>PROCESS 01</div>
              <div className={styles.nodeTitle}>Mesin Cetak A</div>
              <div className={styles.nodeWorkerPill}>👤 Ahmad Fauzi</div>
              <span className={styles.nodeStatusAmber}>⚡ Load 92%</span>
            </div>

            <div className={styles.flowConnector}>
              <span className={styles.connectorLine} />
              <span className={styles.connectorArrow}>FLOW ➔</span>
            </div>

            <div className={styles.flowNodeCard}>
              <div className={styles.nodeKindBadge}>PROCESS 02</div>
              <div className={styles.nodeTitle}>Optic Sorter</div>
              <div className={styles.nodeWorkerPill}>🤖 Robotic Feeder</div>
              <span className={styles.nodeStatusGreen}>✓ AUTOMATED</span>
            </div>

            <div className={styles.flowConnector}>
              <span className={styles.connectorLine} />
              <span className={styles.connectorArrow}>FLOW ➔</span>
            </div>

            <div className={styles.flowNodeCard}>
              <div className={styles.nodeKindBadge}>PROCESS 03</div>
              <div className={styles.nodeTitle}>Sortir Pro QA</div>
              <div className={styles.nodeWorkerPill}>👤 Dewi Ayu (QC)</div>
              <span className={styles.nodeStatusGreen}>✓ OPTIMAL</span>
            </div>
          </div>

          <div className={styles.mockupFooterBar}>
            <div className={styles.mockupFooterLeft}>
              <span className={styles.aiTagBadge}>AI RL CONVERGED</span>
              <span className={styles.mockupFooterText}>
                3 Skenario Optimasi Siap Diterapkan: Skenario 1 (+25%), Skenario 2 (+42.8%), Skenario 3 (+78.6%)
              </span>
            </div>
            <button
              type="button"
              className={styles.mockupInspectBtn}
              onClick={() => navigate("/rec_1")}
            >
              Buka Laporan →
            </button>
          </div>
        </div>
      </section>

      {/* 4. CORE FEATURES (BENTO SHOWCASE) */}
      <section id="fitur" className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionEyebrow}>FITUR UNGGULAN PLATFORM</span>
          <h2 className={styles.sectionHeading}>
            Teknologi Terpadu untuk Transformasi Manufaktur Cerdas
          </h2>
          <p className={styles.sectionSubheading}>
            Menghubungkan visualisasi spasial bebas, simulasi fisika operasional, dan model komputasi kecerdasan buatan.
          </p>
        </div>

        <div className={styles.bentoGrid}>
          {/* Card 1: Interactive Canvas */}
          <div className={`${styles.bentoCard} ${styles.bentoLarge}`}>
            <div className={styles.bentoIcon}>🎨</div>
            <h3 className={styles.bentoTitle}>Interactive Canvas Workspace</h3>
            <p className={styles.bentoDesc}>
              Desain layout pabrik secara bebas dengan gaya papan gambar interaktif. Tambahkan proses, stasiun sortir,
              jalur konveyor, dan tugaskan operator melalui relasi garis FLOW dan ASSIGNED_TO.
            </p>
            <div className={styles.bentoPills}>
              <span>Spasial Bebas</span>
              <span>Clean JSON Extraction</span>
              <span>Template Siap Pakai</span>
            </div>
          </div>

          {/* Card 2: AI RL Optimization Engine */}
          <div className={`${styles.bentoCard} ${styles.bentoLarge}`}>
            <div className={styles.bentoIcon}>🧠</div>
            <h3 className={styles.bentoTitle}>AI Reinforcement Learning Engine</h3>
            <p className={styles.bentoDesc}>
              Secara otomatis menghasilkan 3 skenario optimasi (Realokasi SDM, Substitusi Mesin Otomatis, dan Full Expansion)
              dengan grafik shift dan estimasi dampak biaya tenaga kerja vs mesin.
            </p>
            <div className={styles.bentoPills}>
              <span>Multi-Objective Reward</span>
              <span>10,000+ Episodes</span>
              <span>Shift Forecasting</span>
            </div>
          </div>

          {/* Card 3: Digital Twin & Simulation */}
          <div className={styles.bentoCard}>
            <div className={styles.bentoIcon}>⚙️</div>
            <h3 className={styles.bentoTitle}>Digital Twin Monitoring</h3>
            <p className={styles.bentoDesc}>
              Pantau pergerakan WIP inventory, utilitas mesin, dan deteksi titik bottleneck antrean secara real-time via stream WebSocket.
            </p>
          </div>

          {/* Card 4: Human Factors & Ergonomics */}
          <div className={styles.bentoCard}>
            <div className={styles.bentoIcon}>🩺</div>
            <h3 className={styles.bentoTitle}>Human Factors & RULA</h3>
            <p className={styles.bentoDesc}>
              Prediksi skor kelelahan (Fatigue Score) dan analisis ergonomis RULA untuk mencegah cedera dan merancang rotasi shift yang adil.
            </p>
          </div>

          {/* Card 5: AI Chatbot & What-If Copilot */}
          <div className={styles.bentoCard}>
            <div className={styles.bentoIcon}>💬</div>
            <h3 className={styles.bentoTitle}>AI Chatbot & What-If Simulator</h3>
            <p className={styles.bentoDesc}>
              Asisten interaktif yang terhubung langsung ke state proyek untuk menguji skenario hipotetis seperti pemotongan budget dan penambahan lembur.
            </p>
          </div>
        </div>
      </section>

      {/* 5. 4-STEP WORKFLOW */}
      <section id="alur-kerja" className={styles.sectionAlternate}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionEyebrow}>CARA KERJA PLATFORM</span>
          <h2 className={styles.sectionHeading}>Alur Kerja dari Konsep hingga Eksekusi Nyata</h2>
          <p className={styles.sectionSubheading}>
            Hanya 4 langkah mudah untuk mentransformasi lini pabrik tradisional menjadi ekosistem teroptimasi AI.
          </p>
        </div>

        <div className={styles.workflowStepsGrid}>
          <div className={styles.workflowStepCard}>
            <span className={styles.stepNumberBadge}>01</span>
            <h3 className={styles.stepTitle}>Pilih Template & Rancang Kanvas</h3>
            <p className={styles.stepDesc}>
              Mulai dari kanvas kosong atau template (Seri/Paralel). Hubungkan proses dan tugaskan operator dengan garis relasi intuitif.
            </p>
          </div>

          <div className={styles.workflowStepCard}>
            <span className={styles.stepNumberBadge}>02</span>
            <h3 className={styles.stepTitle}>Tetapkan Batas Operasional</h3>
            <p className={styles.stepDesc}>
              Tentukan batasan anggaran, izin lembur, kebijakan rekrutmen, atau outsourcing bersama AI Agent.
            </p>
          </div>

          <div className={styles.workflowStepCard}>
            <span className={styles.stepNumberBadge}>03</span>
            <h3 className={styles.stepTitle}>Kalkulasi 3 Skenario AI</h3>
            <p className={styles.stepDesc}>
              Tekan "Mulai Analisis AI". Evaluasi chart pergeseran throughput shift, perbandingan biaya, dan status stasiun.
            </p>
          </div>

          <div className={styles.workflowStepCard}>
            <span className={styles.stepNumberBadge}>04</span>
            <h3 className={styles.stepTitle}>Terapkan & Simulasi Digital Twin</h3>
            <p className={styles.stepDesc}>
              Pilih skenario terbaik dan aktifkan pada Digital Twin untuk memonitor hasil peningkatan produktivitas riil.
            </p>
          </div>
        </div>
      </section>

      {/* 6. INTERACTIVE ROI CALCULATOR MINI-WIDGET */}
      <section id="kalkulator" className={styles.section}>
        <div className={styles.roiCardContainer}>
          <div className={styles.roiLeftCol}>
            <span className={styles.roiEyebrow}>INTERACTIVE ROI SIMULATOR</span>
            <h2 className={styles.roiHeading}>Hitung Estimasi Peningkatan Produksi Pabrik Anda</h2>
            <p className={styles.roiDesc}>
              Sesuaikan jumlah operator dan throughput awal pabrik Anda saat ini untuk melihat simulasi dampak implementasi optimasi AI Pabrikers.
            </p>

            <div className={styles.sliderGroup}>
              <div className={styles.sliderLabelRow}>
                <span>Jumlah Operator di Lini:</span>
                <strong className={styles.sliderValText}>{operatorCount} Orang</strong>
              </div>
              <input
                type="range"
                min="5"
                max="100"
                step="1"
                value={operatorCount}
                onChange={(e) => setOperatorCount(Number(e.target.value))}
                className={styles.rangeSlider}
              />
            </div>

            <div className={styles.sliderGroup}>
              <div className={styles.sliderLabelRow}>
                <span>Throughput Saat Ini:</span>
                <strong className={styles.sliderValText}>{currentThroughput} Unit / Jam</strong>
              </div>
              <input
                type="range"
                min="200"
                max="2500"
                step="50"
                value={currentThroughput}
                onChange={(e) => setCurrentThroughput(Number(e.target.value))}
                className={styles.rangeSlider}
              />
            </div>
          </div>

          <div className={styles.roiRightCol}>
            <div className={styles.roiResultBox}>
              <div className={styles.roiResultItem}>
                <span className={styles.roiMetricTag}>PROYEKSI THROUGHPUT BARU</span>
                <div className={styles.roiBigNumber}>
                  {roiCalculations.newThroughput} <span className={styles.roiUnit}>unit/jam</span>
                </div>
                <span className={styles.roiDeltaBadge}>{roiCalculations.potentialGainPercent} Peningkatan Output</span>
              </div>

              <div className={styles.roiResultDivider} />

              <div className={styles.roiMiniMetricsGrid}>
                <div className={styles.roiMiniItem}>
                  <span className={styles.roiMiniLabel}>Estimasi Efisiensi Bulanan</span>
                  <span className={styles.roiMiniVal}>{roiCalculations.monthlySaving}</span>
                </div>
                <div className={styles.roiMiniItem}>
                  <span className={styles.roiMiniLabel}>Estimasi Waktu Balik Modal</span>
                  <span className={styles.roiMiniVal}>{roiCalculations.paybackPeriod}</span>
                </div>
              </div>

              <button
                type="button"
                className={styles.roiCtaBtn}
                onClick={() => navigate("/intro")}
              >
                Uji Pada Model Pabrik Anda →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 7. FAQ ACCORDION */}
      <section id="faq" className={styles.sectionAlternate}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionEyebrow}>PERTANYAAN UMUM</span>
          <h2 className={styles.sectionHeading}>Hal yang Sering Ditanyakan</h2>
        </div>

        <div className={styles.faqList}>
          {FAQS.map((faq, idx) => {
            const isOpen = openFaqIndex === idx;
            return (
              <div key={idx} className={`${styles.faqCard} ${isOpen ? styles.faqCardOpen : ""}`}>
                <button
                  type="button"
                  className={styles.faqQuestionBtn}
                  onClick={() => toggleFaq(idx)}
                  aria-expanded={isOpen}
                >
                  <span className={styles.faqQuestionText}>{faq.q}</span>
                  <span className={styles.faqChevron}>{isOpen ? "−" : "+"}</span>
                </button>
                {isOpen && <p className={styles.faqAnswerText}>{faq.a}</p>}
              </div>
            );
          })}
        </div>
      </section>

      {/* 8. BOTTOM CTA BANNER */}
      <section className={styles.ctaBannerSection}>
        <div className={styles.ctaBannerCard}>
          <div className={styles.ctaBannerContent}>
            <h2 className={styles.ctaBannerTitle}>Siap Merevolusi Efisiensi Lini Manufaktur Anda?</h2>
            <p className={styles.ctaBannerSubtitle}>
              Mulai buat desain alur pertama Anda dalam hitungan menit tanpa instalasi rumit.
            </p>
            <button
              type="button"
              className={styles.ctaBannerPrimaryBtn}
              onClick={() => navigate("/intro")}
            >
              <span>Buka Interactive Canvas Workspace</span>
              <span className={styles.btnArrow}>→</span>
            </button>
          </div>
        </div>
      </section>

      {/* 9. FOOTER */}
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrandCol}>
            <div className={styles.navBrand}>
              <div className={styles.brandLogoBox}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.4">
                  <path d="M3 3v18h18" />
                  <path d="m19 9-5 5-4-4-3 3" />
                </svg>
              </div>
              <span className={styles.brandName}>Pabrikers</span>
            </div>
            <p className={styles.footerDesc}>
              Platform orkestrasi lini manufaktur berbasis kanvas interaktif dan simulasi AI Reinforcement Learning terpadu.
            </p>
          </div>

          <div className={styles.footerLinksCol}>
            <h4 className={styles.footerHeading}>Navigasi Cepat</h4>
            <Link to="/intro" className={styles.footerLink}>Interactive Canvas</Link>
            <Link to="/dashboard" className={styles.footerLink}>Saved Drafts</Link>
            <Link to="/rec_1" className={styles.footerLink}>Analytics Report</Link>
            <Link to="/digital-twin" className={styles.footerLink}>Digital Twin</Link>
          </div>

          <div className={styles.footerLinksCol}>
            <h4 className={styles.footerHeading}>Sistem</h4>
            <span className={styles.systemStatusPill}>
              <span className={styles.pulseDot} />
              AI Engine Operational
            </span>
            <span className={styles.footerCopy}>© {new Date().getFullYear()} Pabrikers Platform. All rights reserved.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
