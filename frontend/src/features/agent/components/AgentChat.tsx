import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useAgentChatStore } from "@/store/agentChat";
import { computeExecutionRounds, toFlowGraph } from "@/features/canvas/utils/flowLogic";
import { askAgent } from "@/features/agent/api/agentChatApi";
import styles from "./AgentChat.module.css";

/** Answers canvas-local intents (summary, help, navigation) without the backend, or returns null. */
function localReply(input: string, navigate: ReturnType<typeof useNavigate>): string | null {
  const { nodes, edges, analysis } = useCanvasUIStore.getState();
  const lower = input.toLowerCase();

  if (/ringkas|summary/.test(lower)) {
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
      "Tanyakan apa saja tentang pabrik, hasil simulasi, atau skenario RL, atau langsung edit di halaman Live.",
    ].join("\n");
  }

  if (/bantu|help|petunjuk|cara|command/.test(lower)) {
    return [
      "Berikut yang bisa saya lakukan:",
      "• 'Ringkas alur produksi' — ringkas node, koneksi, & urutan eksekusi",
      "• Pertanyaan bebas — dijawab AI dari digital twin, hasil simulasi, dan skenario RL",
      "• 'Buka Live' — pindah ke halaman Live untuk mengubah kanvas",
      "Kamu juga bisa bolak-balik lewat tombol Live / Agent di atas.",
    ].join("\n");
  }

  if (/live|kanvas|canvas|board|ubah/.test(lower)) {
    navigate("/live");
    return "Membuka halaman Live agar kamu bisa melihat & mengubah kanvas…";
  }

  return null;
}

/** Offline reply used when the backend chatbot is unreachable. */
function fallbackReply(): string {
  const { nodes, edges } = useCanvasUIStore.getState();
  return [
    "Chatbot AI sedang tidak dapat dihubungi.",
    `Canvas kamu: ${nodes.length} node, ${edges.length} koneksi.`,
    "Ketik 'Ringkas alur produksi' atau 'Buka Live' untuk sementara.",
  ].join("\n");
}

/** Sends a message to the backend chatbot with history, unless a local intent handles it. */
async function buildReply(
  input: string,
  navigate: ReturnType<typeof useNavigate>,
  history: ReturnType<typeof useAgentChatStore.getState>["messages"]
): Promise<string> {
  const local = localReply(input, navigate);
  if (local) return local;
  try {
    const { reply } = await askAgent(input, history, {
      factoryId: useCanvasUIStore.getState().factoryId,
    });
    return reply || fallbackReply();
  } catch {
    return fallbackReply();
  }
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
    const history = useAgentChatStore.getState().messages;
    setInput("");
    pushMessage("user", trimmed);
    setBusy(true);
    try {
      const reply = await buildReply(trimmed, navigate, history);
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