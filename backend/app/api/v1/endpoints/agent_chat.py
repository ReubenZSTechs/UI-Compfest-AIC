"""Chat endpoint that answers with the existing chatbot agents, grounded on twin, simulation and RL data."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.optimization import scenario_store
from app.services.agent_registry_service import AgentRole, get_agent_registry

logger = logging.getLogger(__name__)

router = APIRouter()

ASSET_FIELDS = {
    "asset_id",
    "asset_name",
    "is_automated",
    "units_available",
    "operational_cost_per_hour",
    "environmental_factors",
}
JOB_FIELDS = {"job_id", "job_title", "stage_id", "assigned_worker_ids", "demands"}
WORKER_FIELDS = {"worker_id", "name", "demographics", "shift_context"}


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4_000)
    factory_id: Optional[str] = None
    scenario_id: Optional[str] = None
    history: list[ChatTurn] = Field(default_factory=list)


class AgentChatContext(BaseModel):
    factory_id: Optional[str] = None
    scenario_id: Optional[str] = None
    has_rl_result: bool = False
    has_simulation: bool = False
    history_turns: int = 0


class AgentChatResponse(BaseModel):
    reply: str
    agent_role: str
    context: AgentChatContext


def trim_history(history: list[ChatTurn]) -> list[dict[str, str]]:
    """Keep the most recent turns, truncate long ones and drop empty messages."""
    limit = max(0, settings.AGENT_CHAT_HISTORY_TURNS)
    max_chars = settings.AGENT_CHAT_MESSAGE_CHARS
    recent = history[-limit:] if limit else []
    return [
        {"role": turn.role, "content": turn.content.strip()[:max_chars]}
        for turn in recent
        if turn.content.strip()
    ]


def _scenario_context(bundle: dict[str, Any], scenario_id: Optional[str]) -> dict[str, Any]:
    """Select the asked scenario (or all three) and keep only workers that actually move."""
    scenarios = bundle.get("scenarios", [])
    selected = [item for item in scenarios if item.get("scenario_id") == scenario_id] or scenarios
    compact = []
    for scenario in selected:
        item = dict(scenario)
        flow = dict(item.get("factory_flow_optimal") or {})
        flow["optimal_staff_positions"] = [
            position
            for position in flow.get("optimal_staff_positions", [])
            if position.get("action") != "stay"
        ]
        item["factory_flow_optimal"] = flow
        compact.append(item)
    return {"meta": bundle.get("meta"), "scenarios": compact}


async def _twin_context(db: AsyncSession, factory_id: str) -> Optional[dict[str, Any]]:
    """Load a compact digital twin view of the factory, or None when it does not exist."""
    service = DigitalTwinService(db)
    if await service.get_factory(factory_id) is None:
        return None
    twin = await service.get_full_twin(factory_id)
    return {
        "factory_info": {
            "factory_name": twin.factory_info.factory_name,
            "workflow_sequence": twin.factory_info.workflow_sequence,
        },
        "assets": [asset.model_dump(include=ASSET_FIELDS) for asset in twin.assets],
        "job_descriptions": [job.model_dump(include=JOB_FIELDS) for job in twin.job_desks],
        "workers": [worker.model_dump(include=WORKER_FIELDS) for worker in twin.workers],
    }


def _build_prompt(context: dict[str, Any], message: str) -> str:
    """Render the CONTEXT block expected by the chatbot agent prompts, followed by the question."""
    return f"CONTEXT\n{json.dumps(context, ensure_ascii=False, default=str)}\n\nPERTANYAAN MANAJER\n{message}"


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Tanya chatbot tentang digital twin, hasil simulasi, dan skenario RL",
)
async def chat_with_agent(
    payload: AgentChatRequest, db: AsyncSession = Depends(get_db)
) -> AgentChatResponse:
    """Route the question to the scenario explainer, twin analyst or general agent with chat history."""
    factory_id = payload.factory_id
    bundle = scenario_store.load_optimization_result(factory_id) if factory_id else None
    simulation_summary = (
        scenario_store.read_json(scenario_store.rl_dir(factory_id) / "inputs" / "simulation_summary.json")
        if factory_id
        else None
    )

    context: dict[str, Any] = {}
    if bundle is not None:
        role = AgentRole.CHATBOT_SCENARIO_EXPLAINER
        context = _scenario_context(bundle, payload.scenario_id)
    else:
        twin = await _twin_context(db, factory_id) if factory_id else None
        if twin is not None:
            role = AgentRole.CHATBOT_TWIN_ANALYST
            context = twin
        else:
            role = AgentRole.CHATBOT_GENERAL
    if simulation_summary and role != AgentRole.CHATBOT_GENERAL:
        context["live_simulation_state"] = simulation_summary

    prompt = _build_prompt(context, payload.message) if context else payload.message
    history = trim_history(payload.history)

    try:
        agent = get_agent_registry().get(role)
        reply = await asyncio.wait_for(
            run_in_threadpool(agent.generate_response, prompt, None, history),
            timeout=settings.AGENT_CHAT_TIMEOUT_SECONDS,
        )
    except Exception as error:
        logger.warning("Chat agent %s gagal: %s", role, error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Layanan chatbot LLM sedang tidak tersedia.",
        ) from error

    return AgentChatResponse(
        reply=(reply or "").strip(),
        agent_role=str(role),
        context=AgentChatContext(
            factory_id=factory_id,
            scenario_id=payload.scenario_id,
            has_rl_result=bundle is not None,
            has_simulation=bool(simulation_summary),
            history_turns=len(history),
        ),
    )
