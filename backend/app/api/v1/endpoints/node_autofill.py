# backend/app/api/v1/endpoints/node_autofill.py
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.services.agent_registry_service import AgentRole, get_agent_registry
from app.services.node_autofill_service import (
    DEFAULT_TARGET_FIELDS,
    NodeAutofillError,
    request_node_autofill,
)

router = APIRouter()

AutofillField = Literal[
    "operator_task",
    "qc_requirement",
    "required_skills",
    "material_input",
    "material_output",
    "material_name",
    "material_unit",
    "cycle_time_seconds",
    "capacity",
    "batch_in",
    "batch_out",
    "cycle_ticks",
    "headcount",
    "lane",
    "job_title",
]


class BaseAutofillModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class NodeAutofillRequest(BaseAutofillModel):
    process_name: str = Field(..., min_length=1, max_length=255)
    operator_task: str = ""
    job_title: str = ""
    required_skills: list[str] = Field(default_factory=list)
    qc_requirement: str = ""
    asset_category: str = "manual_station"
    automation_level: Literal["manual", "semi_automated", "automated"] = "manual"
    cycle_time_seconds: float = Field(default=60.0, gt=0)
    noise_level_db: float | None = None
    physical_strain_index: float = Field(default=0.0, ge=0, le=1)
    material_input: list[str] = Field(default_factory=list)
    material_output: list[str] = Field(default_factory=list)
    headcount: int = Field(default=1, ge=1)
    upstream_names: list[str] = Field(default_factory=list)
    downstream_names: list[str] = Field(default_factory=list)
    target_fields: list[AutofillField] = Field(default_factory=list)


class NodeAutofillDemands(BaseAutofillModel):
    required_cognitive_focus: float = Field(..., ge=0, le=1)
    physical_demand_level: Literal["low", "medium", "high"]
    task_complexity: float = Field(..., ge=0, le=1)
    error_severity: Literal["low", "moderate", "high", "critical"]


class NodeAutofillSuggestions(BaseAutofillModel):
    operator_task: str | None = None
    qc_requirement: str | None = None
    required_skills: list[str] | None = None
    material_input: list[str] | None = None
    material_output: list[str] | None = None
    material_name: str | None = None
    material_unit: str | None = None
    cycle_time_seconds: float | None = None
    capacity: float | None = None
    batch_in: float | None = None
    batch_out: float | None = None
    cycle_ticks: int | None = None
    headcount: int | None = None
    lane: str | None = None
    job_title: str | None = None


class NodeAutofillResponse(BaseAutofillModel):
    demands: NodeAutofillDemands
    suggestions: NodeAutofillSuggestions = Field(default_factory=NodeAutofillSuggestions)
    reasoning: str


def _line(label: str, value: Any, fallback: str = "tidak disebutkan") -> str:
    text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value or "")
    return f"{label}: {text.strip() or fallback}"


def _build_prompt(payload: NodeAutofillRequest) -> str:
    noise = f"{payload.noise_level_db} dB" if payload.noise_level_db is not None else "tidak diukur"
    targets = payload.target_fields or list(DEFAULT_TARGET_FIELDS)

    lines = [
        _line("Nama proses", payload.process_name),
        _line("Judul pekerjaan", payload.job_title),
        _line("Tugas operator", payload.operator_task),
        _line("Skill yang dibutuhkan", payload.required_skills),
        _line("Syarat QC", payload.qc_requirement),
        _line("Kategori aset", payload.asset_category, "manual_station"),
        _line("Level otomasi", payload.automation_level, "manual"),
        f"Cycle time: {payload.cycle_time_seconds} detik",
        f"Tingkat kebisingan: {noise}",
        f"Physical strain index: {payload.physical_strain_index}",
        _line("Material input", payload.material_input),
        _line("Material output", payload.material_output),
        f"Headcount: {payload.headcount}",
        _line("Stasiun sebelum", payload.upstream_names, "tidak ada"),
        _line("Stasiun sesudah", payload.downstream_names, "tidak ada"),
        f"TARGET FIELDS: {', '.join(targets)}",
    ]

    return "\n".join(lines)


@router.post(
    "/node-autofill",
    response_model=NodeAutofillResponse,
    response_model_by_alias=True,
    summary="Auto-fill metrik & atribut satu node proses kanvas",
)
async def autofill_node_demands(payload: NodeAutofillRequest) -> NodeAutofillResponse:
    agent = get_agent_registry().get(AgentRole.NODE_AUTOFILL)

    try:
        raw = await run_in_threadpool(
            request_node_autofill, agent, _build_prompt(payload)
        )
    except NodeAutofillError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent auto-fill gagal menghasilkan metrik: {error}",
        ) from error

    suggestions = raw.get("suggestions")

    return NodeAutofillResponse(
        demands=NodeAutofillDemands(**raw["demands"]),
        suggestions=NodeAutofillSuggestions(
            **(suggestions if isinstance(suggestions, dict) else {})
        ),
        reasoning=str(raw.get("reasoning") or ""),
    )