# backend/app/api/v1/endpoints/node_autofill.py
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.services.agent_registry_service import AgentRole, get_agent_registry

router = APIRouter()


class BaseAutofillModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class NodeAutofillRequest(BaseAutofillModel):
    process_name: str = Field(..., min_length=1, max_length=255)
    operator_task: str = ""
    required_skills: list[str] = Field(default_factory=list)
    qc_requirement: str = ""
    asset_category: str = "manual_station"
    automation_level: Literal["manual", "semi_automated", "automated"] = "manual"
    cycle_time_seconds: float = Field(default=60.0, gt=0)
    noise_level_db: float | None = None
    physical_strain_index: float = Field(default=0.0, ge=0, le=1)
    material_input: list[str] = Field(default_factory=list)
    headcount: int = Field(default=1, ge=1)


class NodeAutofillDemands(BaseAutofillModel):
    required_cognitive_focus: float = Field(..., ge=0, le=1)
    physical_demand_level: Literal["low", "medium", "high"]
    task_complexity: float = Field(..., ge=0, le=1)
    error_severity: Literal["low", "moderate", "high", "critical"]


class NodeAutofillResponse(BaseAutofillModel):
    demands: NodeAutofillDemands
    reasoning: str


def _build_prompt(payload: NodeAutofillRequest) -> str:
    skills = ", ".join(payload.required_skills) or "tidak disebutkan"
    materials = ", ".join(payload.material_input) or "tidak disebutkan"
    noise = f"{payload.noise_level_db} dB" if payload.noise_level_db is not None else "tidak diukur"

    return (
        f"Nama proses: {payload.process_name}\n"
        f"Tugas operator: {payload.operator_task or 'tidak disebutkan'}\n"
        f"Skill yang dibutuhkan: {skills}\n"
        f"Syarat QC: {payload.qc_requirement or 'tidak disebutkan'}\n"
        f"Kategori aset: {payload.asset_category}\n"
        f"Level otomasi: {payload.automation_level}\n"
        f"Cycle time: {payload.cycle_time_seconds} detik\n"
        f"Tingkat kebisingan: {noise}\n"
        f"Physical strain index: {payload.physical_strain_index}\n"
        f"Material input: {materials}\n"
        f"Headcount: {payload.headcount}"
    )


@router.post(
    "/node-autofill",
    response_model=NodeAutofillResponse,
    response_model_by_alias=True,
    summary="Auto-fill metrik beban kerja satu node proses kanvas",
)
async def autofill_node_demands(payload: NodeAutofillRequest) -> NodeAutofillResponse:
    agent = get_agent_registry().get(AgentRole.NODE_AUTOFILL)

    try:
        result = await run_in_threadpool(
            agent.generate_structured, user_prompt=_build_prompt(payload)
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent auto-fill gagal menghasilkan metrik: {error}",
        ) from error

    raw = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    demands = raw.get("demands")
    if not isinstance(demands, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent auto-fill mengembalikan struktur tanpa blok 'demands'.",
        )

    return NodeAutofillResponse(
        demands=NodeAutofillDemands(**demands),
        reasoning=str(raw.get("reasoning") or ""),
    )