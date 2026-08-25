from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, Optional, Sequence

DEMAND_KEYS = (
    "required_cognitive_focus",
    "physical_demand_level",
    "task_complexity",
    "error_severity",
)

PLACEHOLDER_FOCUS = {0.0, 0.5}
PLACEHOLDER_COMPLEXITY = {0.0, 0.5}
PLACEHOLDER_TEXT = {"", "n/a", "na", "tidak diketahui", "unknown", "-"}

DEFAULT_TARGET_FIELDS = (
    "operator_task",
    "qc_requirement",
    "required_skills",
    "material_input",
    "material_output",
)


class NodeAutofillError(RuntimeError):
    pass


def _text(value: Any, fallback: str = "tidak disebutkan") -> str:
    text = str(value or "").strip()
    return text if text and text.casefold() not in PLACEHOLDER_TEXT else fallback


def _joined(values: Any, fallback: str = "tidak disebutkan") -> str:
    if not isinstance(values, (list, tuple)):
        return fallback
    items = [str(item).strip() for item in values if str(item).strip()]
    return ", ".join(items) if items else fallback


def is_demand_incomplete(demands: Any) -> bool:
    if not isinstance(demands, dict):
        return True

    if any(demands.get(key) in (None, "") for key in DEMAND_KEYS):
        return True

    focus = demands.get("required_cognitive_focus")
    complexity = demands.get("task_complexity")

    return focus in PLACEHOLDER_FOCUS and complexity in PLACEHOLDER_COMPLEXITY


def build_node_prompt(
    job: dict[str, Any],
    stage: dict[str, Any],
    asset: dict[str, Any],
    neighbours: Sequence[str] = (),
    target_fields: Sequence[str] = (),
) -> str:
    environment = asset.get("environmental_factors") or {}
    noise = environment.get("noise_level_db")
    strain = environment.get("physical_strain_index", 0.0)

    lines = [
        f"Nama proses: {_text(stage.get('stage_name') or job.get('job_title'))}",
        f"Tugas operator: {_text(stage.get('operator_task'))}",
        f"Judul pekerjaan: {_text(job.get('job_title'))}",
        f"Skill yang dibutuhkan: {_joined(job.get('required_skills'))}",
        f"Syarat QC: {_text(stage.get('qc_requirement') or job.get('qc_requirement'))}",
        f"Kategori aset: {_text(asset.get('category'), 'manual_station')}",
        f"Level otomasi: {_text(stage.get('automation_level'), 'manual')}",
        f"Cycle time: {stage.get('cycle_time_seconds') or 60} detik",
        f"Tingkat kebisingan: {f'{noise} dB' if noise is not None else 'tidak diukur'}",
        f"Physical strain index: {strain}",
        f"Material input: {_joined(stage.get('material_input'))}",
        f"Material output: {_joined(stage.get('material_output'))}",
        f"Headcount: {job.get('headcount') or 1}",
    ]

    if neighbours:
        lines.append(f"Stasiun tetangga pada alur: {', '.join(neighbours)}")

    if target_fields:
        lines.append(f"TARGET FIELDS: {', '.join(target_fields)}")

    return "\n".join(lines)


def _neighbours_of(stage_id: str, edges: Iterable[dict[str, Any]],
                   names: dict[str, str]) -> list[str]:
    labels: list[str] = []

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if edge.get("from_stage_id") == stage_id:
            labels.append(f"setelah -> {names.get(edge.get('to_stage_id'), '?')}")
        elif edge.get("to_stage_id") == stage_id:
            labels.append(f"sebelum -> {names.get(edge.get('from_stage_id'), '?')}")

    return labels[:4]


def request_node_autofill(agent: Any, prompt: str, max_attempts: int = 2,
                          backoff_seconds: float = 1.0) -> dict[str, Any]:
    last_error: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = agent.generate_structured(user_prompt=prompt)

            if not isinstance(result, dict):
                raise ValueError("respons agent bukan objek JSON")

            demands = result.get("demands")
            if not isinstance(demands, dict):
                raise ValueError("respons agent tidak memuat blok demands")

            missing = [key for key in DEMAND_KEYS if key not in demands]
            if missing:
                raise ValueError(f"demands kekurangan field: {missing}")

            return result

        except Exception as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    raise NodeAutofillError(last_error or "kegagalan tidak diketahui")


def autofill_factory_job_demands(
    factory_structure: dict[str, Any],
    agent: Any,
    max_workers: int = 4,
    max_attempts: int = 2,
    force: bool = False,
    strict: bool = False,
    progress: Optional[Callable[[int, int], None]] = None,
) -> dict[str, Any]:
    if agent is None:
        raise ValueError("Agent auto-fill node wajib disediakan.")

    jobs = [job for job in factory_structure.get("job_descriptions", []) if isinstance(job, dict)]
    stages = {
        stage.get("stage_id"): stage
        for stage in factory_structure.get("process_stages", [])
        if isinstance(stage, dict)
    }
    assets = {
        asset.get("asset_id"): asset
        for asset in factory_structure.get("assets", [])
        if isinstance(asset, dict)
    }

    factory_info = factory_structure.get("factory_info") or {}
    edges = factory_info.get("process_edges") or []
    stage_names = {
        stage_id: str(stage.get("stage_name") or stage_id)
        for stage_id, stage in stages.items()
    }

    targets = [job for job in jobs if force or is_demand_incomplete(job.get("demands"))]
    total = len(targets)

    if total == 0:
        return {"filled_count": 0, "skipped_count": len(jobs), "failures": [], "reasonings": {}}

    def run(job: dict[str, Any]) -> dict[str, Any]:
        stage = stages.get(job.get("stage_id"), {})
        asset = assets.get(job.get("assigned_asset_id"), {})
        prompt = build_node_prompt(
            job=job,
            stage=stage,
            asset=asset,
            neighbours=_neighbours_of(job.get("stage_id"), edges, stage_names),
            target_fields=DEFAULT_TARGET_FIELDS,
        )

        try:
            return {"job_id": job.get("job_id"), "result": request_node_autofill(
                agent, prompt, max_attempts=max_attempts
            )}
        except NodeAutofillError as error:
            return {"job_id": job.get("job_id"), "error": str(error)}

    results: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        for done, outcome in enumerate(pool.map(run, targets), start=1):
            if "result" in outcome:
                results[outcome["job_id"]] = outcome["result"]
            else:
                failures.append(outcome)

            if progress is not None:
                progress(done, total)

    if failures and strict:
        raise NodeAutofillError(f"{len(failures)} dari {total} node gagal di-autofill.")

    reasonings: dict[str, str] = {}

    for job in targets:
        payload = results.get(job.get("job_id"))
        if payload is None:
            continue

        job["demands"] = payload["demands"]
        reasoning = str(payload.get("reasoning") or "").strip()

        if reasoning:
            reasonings[job.get("job_id")] = reasoning
            existing = str(job.get("metric_derivation_reasoning") or "").strip()
            job["metric_derivation_reasoning"] = (
                f"{existing} | auto-fill: {reasoning}" if existing else f"auto-fill: {reasoning}"
            )

        suggestions = payload.get("suggestions")
        if isinstance(suggestions, dict):
            _apply_suggestions(job, stages.get(job.get("stage_id"), {}), suggestions)

    return {
        "filled_count": len(results),
        "skipped_count": len(jobs) - total,
        "failures": failures,
        "reasonings": reasonings,
    }


def _apply_suggestions(job: dict[str, Any], stage: dict[str, Any],
                       suggestions: dict[str, Any]) -> None:
    stage_text_fields = ("operator_task", "qc_requirement", "lane")
    stage_list_fields = ("material_input", "material_output")

    for key in stage_text_fields:
        value = str(suggestions.get(key) or "").strip()
        if value and not str(stage.get(key) or "").strip():
            stage[key] = value

    for key in stage_list_fields:
        value = suggestions.get(key)
        if isinstance(value, list) and value and not stage.get(key):
            stage[key] = [str(item).strip() for item in value if str(item).strip()]

    cycle = suggestions.get("cycle_time_seconds")
    if isinstance(cycle, (int, float)) and cycle > 0 and not stage.get("cycle_time_seconds"):
        stage["cycle_time_seconds"] = float(cycle)

    title = str(suggestions.get("job_title") or "").strip()
    if title and not str(job.get("job_title") or "").strip():
        job["job_title"] = title