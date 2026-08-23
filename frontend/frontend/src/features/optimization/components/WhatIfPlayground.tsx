// frontend/src/features/optimization/components/WhatIfPlayground.tsx
// AI Chatbot & What-If Simulator:
// Menggunakan riwayat chat aktual dari useAgentChatStore (single source of truth).
// Percakapan yang terjadi di sini langsung tersinkronisasi ke ProjectDraft.
import { useState, useRef, useEffect } from "react";
import { useAgentChatStore } from "@/store/agentChat";
import { useDraftStore } from "@/store/draftStore";
import type { ScenarioData } from "../data/analyticsScenariosData";
import styles from "./WhatIfPlayground.module.css";

interface Props {
  scenarioNumber: number;
  scenarioTitle: string;
  scenarioData?: ScenarioData;
  quickScenarios: string[];
  onWhatIfSimulated?: (query: string) => void;
}

function getFormattedTime(): string {
  return new Date().toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function generateSmartReply(query: string, scTitle: string, scNum: number, sc?: ScenarioData): string {
  const lower = query.toLowerCase();

  if (lower.includes("budget") || lower.includes("biaya") || lower.includes("potong")) {
    return `[Simulasi What-If: Budget Adjustment — Skenario ${scNum}]\n` +
      `Jika anggaran disesuaikan -30%, alokasi pergeseran operator diprioritaskan pada pos paling kritis (Optic Sorter). ` +
      `Estimasi kenaikan throughput tetap mencapai +19.5% (dari baseline) dengan efisiensi biaya optimal.`;
  }

  if (lower.includes("otomasi") || lower.includes("mesin") || lower.includes("robot")) {
    return `[Simulasi What-If: Otomasi Modul — Skenario ${scNum}]\n` +
      `Penggunaan modul otomatisasi pada titik sortir mengurangi cycle time sebesar 35 detik per batch. ` +
      `Tingkat error manusia ditekan hingga ke level minimal (${sc?.metrics.errorRate.after || "<3%"}).`;
  }

  if (lower.includes("phk") || lower.includes("kurang") || lower.includes("pekerja")) {
    return `[Simulasi What-If: Reduksi Operator]\n` +
      `Pengurangan 2 operator akan memicu bottleneck baru di stasiun Sortir Pro (+28% antrean). ` +
      `Disarankan menerapkan rotasi shift atau modul semi-otomatis untuk menjaga target output.`;
  }

  if (lower.includes("demand") || lower.includes("permintaan") || lower.includes("target")) {
    return `[Simulasi What-If: Fluktuasi Demand]\n` +
      `Kapasitas lini pada ${scTitle} mampu menyerap lonjakan demand hingga 1.400 unit/jam. ` +
      `Utilisasi mesin berada pada rentang ideal 82%–88% tanpa risiko overheating.`;
  }

  if (lower.includes("skenario") || lower.includes("banding") || lower.includes("beda")) {
    return `[Analisis Perbandingan Skenario]\n` +
      `• Skenario 1: Realokasi SDM murni (Biaya terendah, throughput +25%)\n` +
      `• Skenario 2: Otomasi robotik selektif (Throughput +42.8%, error turun drastis)\n` +
      `• Skenario 3: Full ekspansi kapasitas (Throughput +78.6% hingga 1.500 u/jam)`;
  }

  return `[AI Assistant — Skenario ${scNum}: ${scTitle}]\n` +
    `Parameter "${query}" telah dianalisis. Konfigurasi alur saat ini stabil dengan throughput ${sc?.metrics.throughput.after || "optimal"}. ` +
    `Ada simulasi atau parameter operasional lain yang ingin Anda uji?`;
}

export function WhatIfPlayground({
  scenarioNumber,
  scenarioTitle,
  scenarioData,
  quickScenarios,
  onWhatIfSimulated,
}: Props) {
  const messages = useAgentChatStore((s) => s.messages);
  const busy = useAgentChatStore((s) => s.busy);
  const pushMessage = useAgentChatStore((s) => s.pushMessage);
  const setBusy = useAgentChatStore((s) => s.setBusy);
  const resetChat = useAgentChatStore((s) => s.resetChat);

  const [input, setInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (!text || busy) return;

    setInput("");
    pushMessage("user", text);
    setBusy(true);

    if (onWhatIfSimulated) {
      onWhatIfSimulated(text);
    }

    // Simulasi respons AI
    setTimeout(() => {
      const reply = generateSmartReply(text, scenarioTitle, scenarioNumber, scenarioData);
      pushMessage("assistant", reply);
      setBusy(false);

      // Sinkronkan ke ProjectDraft aktif
      useDraftStore.getState().syncActiveDraft();
    }, 750);
  }

  function handleClearChat() {
    resetChat();
    useDraftStore.getState().syncActiveDraft();
  }

  return (
    <aside className={styles.chatbotCard} aria-label="AI Chatbot & What-If Simulator">
      {/* 1. HEADER */}
      <div className={styles.header}>
        <div className={styles.headerTitleRow}>
          <div className={styles.aiBadge}>
            <span className={styles.aiPulseDot} />
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
              <rect x="4" y="8" width="16" height="12" rx="2" />
              <circle cx="9" cy="13" r="1" fill="currentColor" />
              <circle cx="15" cy="13" r="1" fill="currentColor" />
              <path d="M9 17h6" />
            </svg>
            <span className={styles.headerTitle}>AI CHATBOT</span>
          </div>

          <div className={styles.headerActions}>
            <span className={styles.scenarioTag}>
              SKENARIO {scenarioNumber}
            </span>
            {messages.length > 0 && (
              <button
                type="button"
                className={styles.clearBtn}
                onClick={handleClearChat}
                title="Hapus riwayat chat sesi ini"
                aria-label="Bersihkan chat"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        <div className={styles.headerSub}>
          <span className={styles.scenarioNameText}>{scenarioTitle}</span>
        </div>
      </div>

      {/* 2. CHAT STREAM / MESSAGES LIST */}
      <div className={styles.chatStream}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>💬</div>
            <h3 className={styles.emptyHeading}>Asisten Produksi AI</h3>
            <p className={styles.emptyText}>
              Riwayat chat dari sesi Agent Anda akan tampil di sini. Tanyakan simulasi What-If,
              dampak perubahan SDM, atau perbandingan skenario.
            </p>
          </div>
        ) : (
          messages.map((m) => {
            const isUser = m.role === "user";
            return (
              <div
                key={m.id}
                className={`${styles.messageRow} ${
                  isUser ? styles.userRow : styles.assistantRow
                }`}
              >
                {!isUser && (
                  <div className={styles.avatarBot} aria-hidden="true">
                    AI
                  </div>
                )}
                <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.botBubble}`}>
                  <div className={styles.bubbleContent}>{m.text}</div>
                  <div className={styles.bubbleMeta}>{getFormattedTime()}</div>
                </div>
              </div>
            );
          })
        )}

        {busy && (
          <div className={`${styles.messageRow} ${styles.assistantRow}`}>
            <div className={styles.avatarBot}>AI</div>
            <div className={`${styles.bubble} ${styles.botBubble} ${styles.typingBubble}`}>
              <span className={styles.typingDot} />
              <span className={styles.typingDot} />
              <span className={styles.typingDot} />
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* 3. QUICK WHAT-IF PROMPT CHIPS */}
      <div className={styles.quickPromptSection}>
        <div className={styles.quickLabel}>SIMULASI WHAT-IF:</div>
        <div className={styles.quickChipsWrap}>
          {quickScenarios.map((qs, i) => (
            <button
              key={i}
              type="button"
              className={styles.quickChip}
              onClick={() => void handleSend(qs)}
              disabled={busy}
            >
              <span className={styles.chipIcon}>⚡</span>
              <span>{qs}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 4. COMPOSER / INPUT BAR */}
      <form
        className={styles.composer}
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
      >
        <input
          type="text"
          className={styles.inputField}
          placeholder={`Tanya AI atau uji What-If Skenario ${scenarioNumber}...`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button
          type="submit"
          className={styles.sendButton}
          disabled={busy || !input.trim()}
          title="Kirim pesan"
          aria-label="Kirim pesan"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="m22 2-7 20-4-9-9-4Z" />
            <path d="M22 2 11 13" />
          </svg>
        </button>
      </form>
    </aside>
  );
}

export default WhatIfPlayground;
