// frontend/src/pages/IntroPage.tsx
// Introduction & Template Selector: choose a workflow layout template
// and launch the interactive canvas.
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

const TEMPLATE_INFO: Record<CanvasTemplateId, { title: string; desc: string }> = {
  blank: {
    title: "Blank Canvas",
    desc: "Start from scratch with a clean, unpopulated layout board.",
  },
  serial: {
    title: "Serial Flow",
    desc: "Linear sequence of sequential workstations with assigned operators.",
  },
  parallel: {
    title: "Parallel Flow",
    desc: "Branching workflow with simultaneous concurrent operations.",
  },
};

const GUIDE_STEPS = [
  {
    title: "1 · Map Out Stations",
    description:
      "Click 'Add Process' and place workstations on your canvas. Arrange sequentially or branch into parallel lines.",
  },
  {
    title: "2 · Assign Staff & Machines",
    description:
      "Add worker and equipment nodes, then connect ASSIGNED_TO lines to their respective workstations.",
  },
  {
    title: "3 · Connect Material Flow",
    description:
      "Link processes together with directional FLOW arrows to represent product movement.",
  },
  {
    title: "4 · Run AI Optimization",
    description:
      "Click 'Start AI Analysis'. Autonomous RL agents test thousands of scenarios and generate ranked improvement cards.",
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
        <span className={styles.eyebrow}>
          Smart Manufacturing · Interactive Canvas Workspace
        </span>
        <h1 className={styles.title}>
          Design your own <span className={styles.accent}>Business Map</span>
        </h1>

        {/* Action Buttons */}
        <div className={styles.heroActions}>
          <button type="button" className={styles.cta} onClick={startCanvas}>
            Start Canvas Design →
          </button>
          <Link
            to={ROUTES.DASHBOARD ?? "/dashboard"}
            className={styles.dashboardBtn}
          >
            Saved Drafts / Dashboard
          </Link>
        </div>
      </section>

      {/* Template picker */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Choose a Starting Template</h2>
        <div className={styles.templateGrid}>
          {TEMPLATE_IDS.map((id) => {
            const meta = TEMPLATE_INFO[id] || TEMPLATE_META[id];
            const counts = CANVAS_TEMPLATES[id]();
            const processCount = counts.nodes.filter(
              (n) => n.data.kind === "process"
            ).length;
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
                <span className={styles.templateBadge}>
                  {edgeCount} connections
                </span>
                <h3 className={styles.templateTitle}>{meta.title}</h3>
                <p className={styles.templateDesc}>{meta.desc}</p>
                <div className={styles.templatePreview} aria-hidden="true">
                  {id === "blank" && (
                    <span className={styles.previewBlank}>Empty Canvas</span>
                  )}
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
                  {processCount} processes · {workerCount} workers
                </span>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          className={styles.secondaryCta}
          onClick={startCanvas}
        >
          Launch Selected Template →
        </button>
      </section>

      {/* Guide Steps */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>How It Works in 4 Steps</h2>
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
