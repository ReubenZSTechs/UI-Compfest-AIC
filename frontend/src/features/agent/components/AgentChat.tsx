// frontend/src/features/agent/components/AgentChat.tsx
// Chatbot bergaya Google Gemini / ChatGPT:
// - Belum ada pesan  => judul + input berada di tengah layar (hero section).
// - Pesan pertama    => input bergeser mulus ke bawah, judul fade-out, dan
//                       area percakapan muncul di tengah (scrollable).
// State messages/busy disimpan di store global (useAgentChatStore) sehingga
// riwayat chat tetap ada saat berpindah antar halaman Live ↔ Agent.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useAgentChatStore } from "@/store/agentChat";
import { computeExecutionRounds, toFlowGraph } from "@/features/canvas/utils/flowLogic";

// [DINONAKTIFKAN SEMENTARA] - Mencegah error TS2307: Cannot find module
// import { runCanvasAnalysis } from "@/features/canvas/utils/runCanvasAnalysis";

import styles from "./AgentChat.module.css";

async function buildReply(input: string, navigate: ReturnType<typeof useNavigate>): Promise<string> {
  const s = useCanvasUIStore.getState();
  const { nodes, edges, analysis } = s;
  const lower = input.toLowerCase();

  if (/analisis|analisa|analy/.test(lower)) {
    if (nodes.length === 0) {
      return "Kanvas masih kosong. Buka halaman Live lalu tambahkan node proses, atau pilih template di Intro.";
    }
    
    // [DINONAKTIFKAN SEMENTARA] - Bypass pemanggilan fungsi yang hilang
    // const result = await runCanvasAnalysis();
    // return result.status === "done"
    //   ? `Analisis AI selesai ✓ ${result.message}`
    //   : `Analisis AI gagal: ${result.message}`;
    
    return "Fitur Analisis AI untuk sementara dinonaktifkan.";
  }

  if (/ringkas|summary|status|berapa/.test(lower)) {
    const processes = nodes.filter((n) => n.data.kind === "process");
    const workers = nodes.filter((n) => n.data.kind === "worker");
    const outputs = nodes.filter((n) => n.data.kind === "output");
    const flowCount = edges.filter((e) => e.data?.relation === "FLOW").length;
    const assignedCount = edges.filter((e) => e.data?.relation === "ASSIGNED_TO").length;
    const rounds = computeExecutionRounds(toFlowGraph(nodes, edges));
    const roundsText = rounds.length
      ? `Urutan eksekusi: ${rounds.map((r, i) => `Round ${i + 1} (${r.join(", ")})`).join(" → ")}`
      : "Urutan eksekusi: belum ada alur FLOW antar proses.";

    return [
      "Ringkasan alur saat ini:",
      `• ${processes.length} proses, ${workers.length} pekerja, ${outputs.length} output.`,
      `• ${edges.length} koneksi (${flowCount} FLOW, ${assignedCount} ASSIGNED_TO).`,
      roundsText,
      `• Status analisis terakhir: ${analysis.status}.`,
      "",
      "Mau saya jalankan analisis AI, atau kamu langsung edit di halaman Live?",
    ].join("\n");
  }

  if (/bantu|help|petunjuk|cara|command/.test(lower)) {
    return [
      "Berikut yang bisa saya lakukan:",
      "• 'Ringkas alur produksi' — ringkas node, koneksi, & urutan eksekusi",
      "• 'Mulai analisis AI' — jalankan analisis dan tandai node di Live (Sedang nonaktif)",
      "• 'Buka Live' — pindah ke halaman Live untuk mengubah kanvas",
      "Kamu juga bisa bolak-balik lewat tombol Live / Agent di atas.",
    ].join("\n");
  }

  if (/live|kanvas|canvas|board|ubah/.test(lower)) {
    navigate("/live");
    return "Membuka halaman Live agar kamu bisa melihat & mengubah kanvas…";
  }

  return [
    "Pesan diterima. Saat ini saya paling andal untuk menganalisis alur produksi.",
    `Canvas kamu: ${nodes.length} node, ${edges.length} koneksi.`,
    "Ketik 'Ringkas alur produksi', 'Mulai analisis AI', atau 'Buka Live'.",
  ].join("\n");
}

export function AgentChat() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const messages = useAgentChatStore((s) => s.messages);
  const busy = useAgentChatStore((s) => s.busy);
  const pushMessage = useAgentChatStore((s) => s.pushMessage);
  const setBusy = useAgentChatStore((s) => s.setBusy);

  // Percakapan dianggap dimulai begitu ada minimal satu pesan.
  const isStarted = messages.length > 0;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setInput("");
    pushMessage("user", trimmed);
    setBusy(true);
    try {
      const reply = await buildReply(trimmed, navigate);
      pushMessage("assistant", reply);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.root}>
      {/* Area percakapan — muncul di atas chatbox setelah pesan pertama. */}
      <div
        className={`${styles.messages} ${isStarted ? styles.messagesActive : ""}`}
        ref={scrollRef}
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={`${styles.bubble} ${m.role === "user" ? styles.userBubble : styles.assistantBubble}`}
          >
            <span className={styles.bubbleText}>{m.text}</span>
          </div>
        ))}
        {busy && (
          <div className={`${styles.bubble} ${styles.assistantBubble} ${styles.typing}`}>
            <span className={styles.typingDots} aria-label="Agent sedang mengetik">
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
          </div>
        )}
      </div>

      {/* Empty state: SATU kontainer flex vertikal = teks sapaan + chatbox.
          Saat pesan pertama dikirim, kontainer bergeser ke bawah, teks fade-out,
          dan area percakapan muncul di atasnya. */}
      <div className={`${styles.heroStack} ${isStarted ? styles.heroStackActive : ""}`}>
        <div className={`${styles.heroText} ${isStarted ? styles.heroTextHidden : ""}`}>
          <span className={styles.descriptionTitle}>Give your greatest idea</span>
          <span className={styles.descriptionSub}>
            Tulis instruksi atau pilih aksi untuk mengoordinasikan alur produksi AI
          </span>
        </div>

        <form
          className={styles.composer}
          onSubmit={(e) => {
            e.preventDefault();
            void send(input);
          }}
        >
          <input
            type="text"
            className={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Tulis pesan ke agent…"
            aria-label="Pesan ke agent"
            disabled={busy}
          />
          <button type="submit" className={styles.sendButton} disabled={busy || !input.trim()}>
            <svg
              width={16}
              height={16}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m22 2-7 20-4-9-9-4z" />
              <path d="M22 2 11 13" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}

export default AgentChat;