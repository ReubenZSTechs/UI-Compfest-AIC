import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { RobotAnimation } from "../components/RobotAnimation";
import styles from "./LandingPage.module.css";

const STEPS = [
  {
    number: "01",
    title: "Draw Your Floor Plan",
    desc: "Map out your workstations and team like drawing on a whiteboard. Simply drag, drop, and connect steps.",
    badge: "Easy Drag & Drop",
  },
  {
    number: "02",
    title: "Let AI Test Scenarios",
    desc: "Our AI automatically tests thousands of what-if situations to find where work slows down and where costs can be saved.",
    badge: "Instant Simulation",
  },
  {
    number: "03",
    title: "Pick the Best Plan",
    desc: "Compare clear recommendations with real profit & time estimates, then apply the best strategy to your business.",
    badge: "Actionable Results",
  },
];

const SCENARIOS = [
  {
    title: "Production Line Balance",
    desc: "Distribute tasks evenly among workers and machines so no station is overwhelmed or left waiting.",
    stat: "+42.8% Output",
  },
  {
    title: "Faster Order Delivery",
    desc: "Find the fastest logistics routes and warehouse paths to get products to customers with less delay.",
    stat: "-35% Lead Time",
  },
  {
    title: "Smart Staff & Machine Allocation",
    desc: "Schedule shifts and assign equipment efficiently without burning out staff or overpaying on overtime.",
    stat: "-28% Cost",
  },
];

const METRICS = [
  { val: "+78.6%", label: "Max Output Increase" },
  { val: "-89.0%", label: "Fewer Production Mistakes" },
  { val: "10,000+", label: "Scenarios Tested Automatically" },
  { val: "< 3s", label: "Instant Plan Check" },
];

const FAQS = [
  {
    q: "How does Pabrikers help my business?",
    a: "Instead of guessing or risking costly trials on your real factory floor, Pabrikers creates a digital playground where AI tests thousands of options to find you the highest output at the lowest cost.",
  },
  {
    q: "Do I need technical or coding skills to use this?",
    a: "Not at all. You can build workflows visually like Miro or Canva—just drag, drop, and click 'Run AI'. The system handles all the complex calculations for you.",
  },
  {
    q: "Can I test 'what-if' questions like budget cuts or adding extra staff?",
    a: "Yes! Simply ask the built-in AI Assistant questions like 'What happens if we add 2 more machines?' and see immediate impact on output and costs.",
  },
  {
    q: "Is my progress saved automatically?",
    a: "Yes, every layout, AI conversation, and recommendation is saved in your workspace so you can pick up anytime.",
  },
];

export function LandingPage() {
  const navigate = useNavigate();
  const [operatorCount, setOperatorCount] = useState<number>(24);
  const [currentThroughput, setCurrentThroughput] = useState<number>(850);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  const roiCalculations = useMemo(() => {
    const potentialGain = Math.round(currentThroughput * 0.428);
    const newThroughput = currentThroughput + potentialGain;
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
      paybackPeriod: "2.5 Months",
    };
  }, [operatorCount, currentThroughput]);

  function toggleFaq(idx: number) {
    setOpenFaqIndex((prev) => (prev === idx ? null : idx));
  }

  return (
    <div className={styles.landingContainer}>
      {/* 1. TOP NAVBAR */}
      <header className={styles.navbar}>
        <div className={styles.navInner}>
          <div className={styles.navLeftGroup}>
            <Link to="/" className={styles.navBrand}>
              <div className={styles.brandLogoBox}>
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="2.4"
                >
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
              <a href="#faq" className={styles.navLink}>
                FAQ
              </a>
            </nav>
          </div>

          <div className={styles.navActions}>
            <Link to="/dashboard" className={styles.profileBtn} aria-label="CIT Admin Profile">
              <div className={styles.profileAvatar}>CIT</div>
              <span className={styles.profileTooltip}>CIT Admin</span>
            </Link>
          </div>
        </div>
      </header>

      {/* 2. HERO SECTION */}
      <section className={styles.heroSection}>
        <div className={styles.heroTwoCol}>
          <div className={styles.heroLeft}>
            <h1 className={styles.heroTitle}>
              <span className={styles.heroTitlePrefix}>Welcome to</span>
              <span className={styles.heroHighlight}>PABRIKERS</span>
            </h1>

            <p className={styles.heroDescription}>
              Your smart AI business partner that tests different operational ideas in a risk-free virtual simulator, clears workflow bottlenecks, and boosts your day-to-day profit.
            </p>

            <div className={styles.heroCtaGroup}>
              <button
                type="button"
                className={styles.heroPrimaryBtn}
                onClick={() => navigate("/intro")}
              >
                <span>Get your canvas</span>
                <span className={styles.heroBtnArrow}>→</span>
              </button>
            </div>

            <div className={styles.heroChips}>
              <span className={styles.heroChip}>Autonomous AI Helpers</span>
              <span className={styles.heroChip}>Smart Cost Optimization</span>
              <span className={styles.heroChip}>Risk-Free Simulations</span>
            </div>
          </div>

          <div className={styles.heroRight}>
            <div className={styles.robotAnimationBox}>
              <RobotAnimation />
            </div>
          </div>
        </div>

        {/* 3. METRICS TICKER STRIP */}
        <div className={styles.heroMetricsStrip}>
          {METRICS.map((m, idx) => (
            <div key={m.label} className={styles.metricItemWrapper}>
              {idx > 0 && <div className={styles.heroMetricDivider} />}
              <div className={styles.heroMetricItem}>
                <span className={styles.metricVal}>{m.val}</span>
                <span className={styles.metricLabel}>{m.label}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. HOW IT WORKS */}
      <section id="how-it-works" className={styles.sectionAlternate}>
        <div className={styles.sectionInner}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionEyebrow}>HOW IT WORKS</span>
            <h2 className={styles.sectionHeading}>How Pabrikers Works</h2>
            <p className={styles.sectionSubheading}>
              Transform your everyday operations into a smooth, cost-efficient workflow in three easy steps.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            {STEPS.map((step) => (
              <div key={step.number} className={styles.stepCard}>
                <div className={styles.stepCardTop}>
                  <span className={styles.stepNumber}>{step.number}</span>
                  <span className={styles.stepBadge}>{step.badge}</span>
                </div>
                <h3 className={styles.stepCardTitle}>{step.title}</h3>
                <p className={styles.stepCardDesc}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5. SUPPORTED SCENARIOS */}
      <section id="scenarios" className={styles.section}>
        <div className={styles.sectionInner}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionEyebrow}>COMMON USE CASES</span>
            <h2 className={styles.sectionHeading}>What You Can Optimize</h2>
            <p className={styles.sectionSubheading}>
              Ready-made templates designed to solve common business and production hurdles.
            </p>
          </div>

          <div className={styles.scenarioGrid}>
            {SCENARIOS.map((s) => (
              <div key={s.title} className={styles.scenarioCard}>
                <div className={styles.scenarioCardTop}>
                  <h3 className={styles.scenarioTitle}>{s.title}</h3>
                  <span className={styles.scenarioStatBadge}>{s.stat}</span>
                </div>
                <p className={styles.scenarioDesc}>{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6. INTERACTIVE ROI CALCULATOR WIDGET */}
      <section id="roi-calculator" className={styles.sectionAlternate}>
        <div className={styles.sectionInner}>
          <div className={styles.roiCardContainer}>
            <div className={styles.roiLeftCol}>
              <span className={styles.roiEyebrow}>INTERACTIVE PROFIT ESTIMATOR</span>
              <h2 className={styles.roiHeading}>
                Estimate Your Business Gains
              </h2>
              <p className={styles.roiDesc}>
                Slide your team size and current output to see how much more you could produce and save with AI workflow optimization.
              </p>

              <div className={styles.sliderGroup}>
                <div className={styles.sliderLabelRow}>
                  <span>Workers on Shift:</span>
                  <strong className={styles.sliderValText}>
                    {operatorCount} People
                  </strong>
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
                  <span>Current Output per Hour:</span>
                  <strong className={styles.sliderValText}>
                    {currentThroughput} Units / Hour
                  </strong>
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
                  <span className={styles.roiMetricTag}>PROJECTED NEW OUTPUT</span>
                  <div className={styles.roiBigNumber}>
                    {roiCalculations.newThroughput}{" "}
                    <span className={styles.roiUnit}>units/hr</span>
                  </div>
                  <span className={styles.roiDeltaBadge}>
                    {roiCalculations.potentialGainPercent} Production Boost
                  </span>
                </div>

                <div className={styles.roiResultDivider} />

                <div className={styles.roiMiniMetricsGrid}>
                  <div className={styles.roiMiniItem}>
                    <span className={styles.roiMiniLabel}>
                      Estimated Monthly Savings
                    </span>
                    <span className={styles.roiMiniVal}>
                      {roiCalculations.monthlySaving}
                    </span>
                  </div>
                  <div className={styles.roiMiniItem}>
                    <span className={styles.roiMiniLabel}>Expected Payback</span>
                    <span className={styles.roiMiniVal}>
                      {roiCalculations.paybackPeriod}
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  className={styles.roiCtaBtn}
                  onClick={() => navigate("/intro")}
                >
                  Try It With Your Team →
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. FAQ ACCORDION */}
      <section id="faq" className={styles.section}>
        <div className={styles.sectionInner}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionEyebrow}>FAQ</span>
            <h2 className={styles.sectionHeading}>
              Frequently Asked Questions
            </h2>
            <p className={styles.sectionSubheading}>
              Simple answers to help you understand how Pabrikers works for your business.
            </p>
          </div>

          <div className={styles.faqList}>
            {FAQS.map((faq, idx) => {
              const isOpen = openFaqIndex === idx;
              return (
                <div
                  key={faq.q}
                  className={`${styles.faqCard} ${isOpen ? styles.faqCardOpen : ""}`}
                >
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
        </div>
      </section>

      {/* 8. BOTTOM CTA BANNER */}
      <section className={styles.ctaBannerSection}>
        <div className={styles.ctaBannerCard}>
          <div className={styles.ctaBannerContent}>
            <h2 className={styles.ctaBannerTitle}>
              Ready to Make Your Operations Smarter and Faster?
            </h2>
            <p className={styles.ctaBannerSubtitle}>
              Draw your first process in minutes and see where you can save time and money—no software setup required.
            </p>
            <button
              type="button"
              className={styles.ctaBannerPrimaryBtn}
              onClick={() => navigate("/intro")}
            >
              <span>Launch Interactive Canvas</span>
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
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="2.4"
                >
                  <path d="M3 3v18h18" />
                  <path d="m19 9-5 5-4-4-3 3" />
                </svg>
              </div>
              <span className={styles.brandName}>Pabrikers</span>
            </div>
            <p className={styles.footerDesc}>
              Smart factory orchestration platform powered by interactive
              canvas design and unified Reinforcement Learning simulation.
            </p>
          </div>

          <div className={styles.footerLinksCol}>
            <h4 className={styles.footerHeading}>Quick Navigation</h4>
            <Link to="/intro" className={styles.footerLink}>
              Interactive Canvas
            </Link>
            <Link to="/dashboard" className={styles.footerLink}>
              Saved Drafts
            </Link>
            <Link to="/rec_1" className={styles.footerLink}>
              Analytics Report
            </Link>
            <Link to="/digital-twin" className={styles.footerLink}>
              Digital Twin
            </Link>
          </div>

          <div className={styles.footerLinksCol}>
            <h4 className={styles.footerHeading}>System Status</h4>
            <span className={styles.systemStatusPill}>
              <span className={styles.pulseDot} />
              AI Engine Operational
            </span>
            <span className={styles.footerCopy}>
              © {new Date().getFullYear()} Pabrikers Platform. All rights
              reserved.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
