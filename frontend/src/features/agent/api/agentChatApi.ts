import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type { AgentChatMessage } from "@/store/agentChat";

export interface AgentChatReply {
  reply: string;
  agent_role: string;
  context: {
    factory_id?: string | null;
    scenario_id?: string | null;
    has_rl_result: boolean;
    has_simulation: boolean;
    history_turns: number;
  };
}

export interface AgentChatOptions {
  factoryId?: string | null;
  scenarioId?: string | null;
}

/** Sends a question with the prior chat history to the backend chatbot agent. */
export async function askAgent(
  message: string,
  history: AgentChatMessage[],
  options: AgentChatOptions = {}
): Promise<AgentChatReply> {
  const { data } = await apiClient.post<AgentChatReply>(
    ENDPOINTS.AGENTS.CHAT,
    {
      message,
      factory_id: options.factoryId ?? null,
      scenario_id: options.scenarioId ?? null,
      history: history.map((item) => ({ role: item.role, content: item.text })),
    },
    { timeout: 60000 }
  );
  return data;
}
