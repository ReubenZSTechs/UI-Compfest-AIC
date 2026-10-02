import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.endpoints import agent_chat
from app.core.config import settings
from app.optimization import scenario_store


class StubAgent:
    def __init__(self, reply="Jawaban uji", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def generate_response(self, user_prompt, extra_args=None, prior_messages=None):
        self.calls.append({"prompt": user_prompt, "prior_messages": prior_messages})
        if self.error:
            raise self.error
        return self.reply


class StubRegistry:
    def __init__(self, agent):
        self.agent = agent
        self.roles = []

    def get(self, role):
        self.roles.append(str(role))
        return self.agent


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(scenario_store, "RL_ROOT", tmp_path)

    async def no_db():
        yield None

    app = FastAPI()
    app.include_router(agent_chat.router, prefix="/agents")
    app.dependency_overrides[get_db] = no_db
    return app


def _install(monkeypatch, agent):
    registry = StubRegistry(agent)
    monkeypatch.setattr(agent_chat, "get_agent_registry", lambda: registry)
    return registry


def test_history_is_trimmed_and_sent_as_prior_messages(client, monkeypatch):
    agent = StubAgent()
    registry = _install(monkeypatch, agent)
    monkeypatch.setattr(settings, "AGENT_CHAT_HISTORY_TURNS", 3)
    monkeypatch.setattr(settings, "AGENT_CHAT_MESSAGE_CHARS", 10)
    history = [
        {"role": "user", "content": "satu"},
        {"role": "assistant", "content": "dua"},
        {"role": "user", "content": "tiga panjang sekali"},
        {"role": "assistant", "content": "   "},
    ]

    response = TestClient(client).post("/agents/chat", json={"message": "Halo", "history": history})

    assert response.status_code == 200
    assert response.json()["reply"] == "Jawaban uji"
    assert registry.roles == ["chatbot_general"]
    assert agent.calls[0]["prior_messages"] == [
        {"role": "assistant", "content": "dua"},
        {"role": "user", "content": "tiga panja"},
    ]
    assert agent.calls[0]["prompt"] == "Halo"
    assert response.json()["context"]["history_turns"] == 2


def test_rl_result_routes_to_scenario_explainer_with_context(client, monkeypatch, tmp_path):
    agent = StubAgent()
    registry = _install(monkeypatch, agent)
    scenario_store.write_json_atomic(
        tmp_path / "fac-1" / "optimal_state.json",
        {
            "hasil_optimisasi_skenario_optimal": {
                "meta": {"factory_id": "fac-1"},
                "scenarios": [
                    {
                        "scenario_id": "scenario_02",
                        "factory_flow_optimal": {
                            "optimal_staff_positions": [
                                {"worker_id": "wrk-01", "action": "stay"},
                                {"worker_id": "wrk-02", "action": "moved"},
                            ]
                        },
                    },
                    {"scenario_id": "scenario_03", "factory_flow_optimal": {}},
                ],
            }
        },
    )
    scenario_store.write_json_atomic(
        tmp_path / "fac-1" / "inputs" / "simulation_summary.json", {"system_bottlenecks": ["baking"]}
    )

    response = TestClient(client).post(
        "/agents/chat",
        json={"message": "Kenapa?", "factory_id": "fac-1", "scenario_id": "scenario_02"},
    )

    assert response.status_code == 200
    assert registry.roles == ["chatbot_scenario_explainer"]
    prompt = agent.calls[0]["prompt"]
    assert prompt.startswith("CONTEXT\n") and prompt.endswith("PERTANYAAN MANAJER\nKenapa?")
    assert '"wrk-02"' in prompt and '"wrk-01"' not in prompt and "scenario_03" not in prompt
    assert '"baking"' in prompt
    assert response.json()["context"]["has_rl_result"] is True


def test_llm_failure_returns_503(client, monkeypatch):
    _install(monkeypatch, StubAgent(error=RuntimeError("down")))
    response = TestClient(client).post("/agents/chat", json={"message": "Halo"})
    assert response.status_code == 503
