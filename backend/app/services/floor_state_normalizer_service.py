from __future__ import annotations

import re
from typing import Any, Iterable

STAGE_ID_KEYS = (
    "current_stage_id",
    "current_station",
    "stage_id",
    "workflow_step",
    "station_id",
)

NEXT_STAGE_KEYS = (
    "moving_to_next_stage_id",
    "moving_to_next_step",
    "next_stage_id",
)

TERMINAL_TOKENS = {
    "finished_goods_storage",
    "finished_goods",
    "finished",
    "finish",
    "selesai",
    "gudang_barang_jadi",
    "none",
    "null",
    "",
}

STEP_PREFIX = re.compile(r"^(?:step|stage|tahap|tahapan)[_\-\s]*\d+[_\-\s]*")


class FloorStateAlignmentError(ValueError):
    pass


def normalize_token(value: Any) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return token.strip("_")


def strip_step_prefix(token: str) -> str:
    return STEP_PREFIX.sub("", token)


def read_jobs(twin: dict[str, Any]) -> list[dict[str, Any]]:
    return twin.get("job_descriptions") or twin.get("job_desks") or []


def job_stage_id(job: dict[str, Any]) -> str | None:
    for key in ("stage_id", "workflow_step"):
        value = job.get(key)
        if value:
            return str(value)
    return None


def stage_sequence(twin: dict[str, Any]) -> list[str]:
    stages = twin.get("process_stages") or []
    ordered = [str(stage["stage_id"]) for stage in stages if stage.get("stage_id")]

    declared = (twin.get("factory_info") or {}).get("workflow_sequence") or []
    known = set(ordered)
    resequenced = [str(item) for item in declared if str(item) in known]

    if len(resequenced) == len(ordered):
        return resequenced

    return ordered


def index_stages(twin: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stages = twin.get("process_stages") or []
    return {str(stage["stage_id"]): stage for stage in stages if stage.get("stage_id")}


def build_stage_alias_map(twin: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}

    def register(alias: Any, stage_id: str) -> None:
        token = normalize_token(alias)
        if not token:
            return
        aliases.setdefault(token, stage_id)
        aliases.setdefault(strip_step_prefix(token), stage_id)

    for stage_id, stage in index_stages(twin).items():
        aliases[stage_id] = stage_id
        register(stage_id, stage_id)
        register(stage.get("stage_name"), stage_id)

    return aliases


def build_asset_stage_map(twin: dict[str, Any]) -> dict[str, str]:
    owners: dict[str, list[str]] = {}

    for stage_id, stage in index_stages(twin).items():
        asset_id = stage.get("asset_id")
        if asset_id:
            owners.setdefault(str(asset_id), []).append(stage_id)

    return {asset_id: stages[0] for asset_id, stages in owners.items() if len(stages) == 1}


def build_worker_stage_map(twin: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for job in read_jobs(twin):
        stage_id = job_stage_id(job)
        if not stage_id:
            continue

        for worker_id in job.get("assigned_worker_ids") or []:
            mapping.setdefault(str(worker_id), stage_id)

    return mapping


def build_allocation_stage_map(twin: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for job in read_jobs(twin):
        stage_id = job_stage_id(job)
        if not stage_id:
            continue

        for key in ("allocation_id", "job_id"):
            value = job.get(key)
            if value:
                mapping.setdefault(str(value), stage_id)

    return mapping


def build_job_index(twin: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    for job in read_jobs(twin):
        stage_id = job_stage_id(job)
        if stage_id:
            index.setdefault(stage_id, job)

    return index


def first_value(source: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


class StageResolver:
    def __init__(self, twin: dict[str, Any]):
        self.stages = index_stages(twin)
        self.sequence = stage_sequence(twin)
        self.aliases = build_stage_alias_map(twin)
        self.by_asset = build_asset_stage_map(twin)
        self.by_worker = build_worker_stage_map(twin)
        self.by_allocation = build_allocation_stage_map(twin)
        self.jobs = build_job_index(twin)

    def by_alias(self, raw: Any) -> str | None:
        if raw in (None, ""):
            return None

        candidate = str(raw)
        if candidate in self.stages:
            return candidate

        token = normalize_token(candidate)
        return self.aliases.get(token) or self.aliases.get(strip_step_prefix(token))

    def next_stage(self, raw: Any, stage_id: str | None) -> str | None:
        if normalize_token(raw) in TERMINAL_TOKENS:
            return None

        resolved = self.by_alias(raw)
        if resolved:
            return resolved

        stage = self.stages.get(stage_id or "") or {}
        if stage.get("is_terminal"):
            return None

        return self.by_alias(stage.get("next_stage_id"))

    def resolve(self, position: dict[str, Any], ordinal: int,
                allow_ordinal: bool = True) -> tuple[str | None, str]:
        resolved = self.by_alias(first_value(position, STAGE_ID_KEYS))
        if resolved:
            return resolved, "stage_id"

        resolved = self.by_asset.get(str(position.get("current_asset_id") or ""))
        if resolved:
            return resolved, "asset_id"

        resolved = self.by_worker.get(str(position.get("worker_id") or ""))
        if resolved:
            return resolved, "worker_allocation"

        resolved = self.by_allocation.get(str(position.get("allocation_id") or ""))
        if resolved:
            return resolved, "allocation_id"

        if allow_ordinal and ordinal < len(self.sequence):
            return self.sequence[ordinal], "ordinal"

        return None, "unresolved"


def normalize_position(position: dict[str, Any], stage_id: str,
                       resolver: StageResolver) -> dict[str, Any]:
    stage = resolver.stages.get(stage_id) or {}
    job = resolver.jobs.get(stage_id) or {}

    return {
        "worker_id": position.get("worker_id"),
        "name": position.get("name"),
        "allocation_id": position.get("allocation_id") or job.get("allocation_id"),
        "current_stage_id": stage_id,
        "lane": position.get("lane") or stage.get("lane") or "main",
        "shift_id": position.get("shift_id") or job.get("shift_id"),
        "current_asset_id": position.get("current_asset_id") or stage.get("asset_id"),
        "activity_status": position.get("activity_status") or "processing",
        "moving_to_next_stage_id": resolver.next_stage(
            first_value(position, NEXT_STAGE_KEYS), stage_id
        ),
        "handoff_item": position.get("handoff_item") or "",
    }


def normalize_evaluations(evaluations: list[dict[str, Any]], resolver: StageResolver,
                          stage_by_worker: dict[str, str]) -> list[dict[str, Any]]:
    normalized = []

    for entry in evaluations or []:
        worker_id = str(entry.get("worker_id") or "")
        stage_id = resolver.by_alias(entry.get("stage_id")) or stage_by_worker.get(worker_id)
        stage = resolver.stages.get(stage_id or "") or {}
        job = resolver.jobs.get(stage_id or "") or {}

        normalized.append({
            **entry,
            "stage_id": stage_id,
            "job_id": entry.get("job_id") or job.get("job_id"),
            "asset_id": entry.get("asset_id") or stage.get("asset_id"),
        })

    return normalized


def normalize_floor_state(twin: dict[str, Any], floor: dict[str, Any],
                          allow_ordinal: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    if not twin:
        raise FloorStateAlignmentError("Struktur pabrik (Agent A) belum tersedia.")

    if not floor:
        raise FloorStateAlignmentError("Kondisi lantai (Agent C) belum tersedia.")

    resolver = StageResolver(twin)

    if not resolver.stages:
        raise FloorStateAlignmentError(
            "process_stages kosong pada struktur pabrik. Jalankan ulang Agent A."
        )

    flow = floor.get("factory_flow_rightnow") or {}
    raw_positions = flow.get("staff_current_positions") or []

    if not raw_positions:
        raise FloorStateAlignmentError(
            "factory_flow_rightnow tidak memuat staff_current_positions."
        )

    positions: list[dict[str, Any]] = []
    sources: list[str] = []
    unresolved: list[dict[str, Any]] = []
    stage_by_worker: dict[str, str] = {}

    for ordinal, raw in enumerate(raw_positions):
        stage_id, source = resolver.resolve(raw, ordinal, allow_ordinal=allow_ordinal)

        if stage_id is None:
            unresolved.append({
                "worker_id": raw.get("worker_id"),
                "stage_terbaca": first_value(raw, STAGE_ID_KEYS),
                "asset_terbaca": raw.get("current_asset_id"),
            })
            continue

        positions.append(normalize_position(raw, stage_id, resolver))
        sources.append(source)
        stage_by_worker[str(raw.get("worker_id") or "")] = stage_id

    if not positions:
        raise FloorStateAlignmentError(
            "Tidak ada satu pun posisi Agent C yang bisa dipetakan ke process_stages. "
            f"stage_id terbaca: {sorted({str(item['stage_terbaca']) for item in unresolved})}. "
            f"stage_id tersedia: {sorted(resolver.stages)}."
        )

    normalized_floor = {
        **floor,
        "factory_flow_rightnow": {
            **flow,
            "staff_current_positions": positions,
        },
        "llm_compatibility_and_evaluations": normalize_evaluations(
            floor.get("llm_compatibility_and_evaluations") or [],
            resolver,
            stage_by_worker,
        ),
    }

    report = {
        "total": len(raw_positions),
        "resolved": len(positions),
        "unresolved": unresolved,
        "sources": {source: sources.count(source) for source in sorted(set(sources))},
        "empty_stages": [
            stage_id for stage_id in resolver.sequence
            if stage_id not in set(stage_by_worker.values())
        ],
    }

    return normalized_floor, report


def build_env_snapshot(twin: dict[str, Any], floor: dict[str, Any],
                       workers: dict[str, Any] | None = None,
                       simulation: dict[str, Any] | None = None,
                       allow_ordinal: bool = True) -> dict[str, Any]:
    normalized_floor, report = normalize_floor_state(twin, floor, allow_ordinal=allow_ordinal)

    resolver = StageResolver(twin)
    flow = normalized_floor["factory_flow_rightnow"]
    positions = flow["staff_current_positions"]

    evaluation_by_worker = {
        str(entry.get("worker_id")): entry
        for entry in normalized_floor["llm_compatibility_and_evaluations"]
    }

    worker_index = {
        str(worker.get("worker_id")): worker
        for worker in (workers or {}).get("workers") or []
    }

    assets = {
        str(asset.get("asset_id")): asset
        for asset in twin.get("assets") or []
    }

    metrics_by_worker = {
        str(item.get("worker_id")): item.get("calculated_realtime_metrics") or {}
        for item in ((simulation or {}).get("live_simulation_state") or {}).get(
            "current_assignments"
        ) or []
    }

    occupancy: dict[str, list[dict[str, Any]]] = {}

    for position in positions:
        worker_id = str(position["worker_id"])
        evaluations = (evaluation_by_worker.get(worker_id) or {}).get("evaluations") or {}
        profile = worker_index.get(worker_id) or {}

        occupancy.setdefault(position["current_stage_id"], []).append({
            "worker_id": worker_id,
            "name": position.get("name"),
            "activity_status": position["activity_status"],
            "asset_id": position["current_asset_id"],
            "demographics": profile.get("demographics") or {},
            "shift_context": profile.get("shift_context") or {},
            "evaluations": evaluations,
            "realtime_metrics": metrics_by_worker.get(worker_id) or {},
        })

    stages = []

    for index, stage_id in enumerate(resolver.sequence):
        stage = resolver.stages[stage_id]
        job = resolver.jobs.get(stage_id) or {}
        asset = assets.get(str(stage.get("asset_id"))) or {}

        stages.append({
            "index": index,
            "stage_id": stage_id,
            "stage_name": stage.get("stage_name"),
            "lane": stage.get("lane") or position.get("lane") or "main",
            "next_stage_id": None if stage.get("is_terminal") else stage.get("next_stage_id"),
            "is_terminal": bool(stage.get("is_terminal")),
            "asset_id": stage.get("asset_id"),
            "asset_name": asset.get("asset_name"),
            "units_available": asset.get("units_available"),
            "automation_level": stage.get("automation_level") or asset.get("automation_level"),
            "cycle_time_seconds": stage.get("cycle_time_seconds"),
            "throughput_per_hour": stage.get("throughput_per_hour"),
            "environmental_factors": asset.get("environmental_factors") or {},
            "job_id": job.get("job_id"),
            "demands": job.get("demands") or {},
            "assigned_workers": occupancy.get(stage_id, []),
        })

    return {
        "factory_id": (twin.get("factory_info") or {}).get("factory_id"),
        "snapshot_timestamp": flow.get("snapshot_timestamp"),
        "note": flow.get("note"),
        "workflow_sequence": resolver.sequence,
        "process_edges": (twin.get("factory_info") or {}).get("process_edges") or [],
        "parallel_groups": (twin.get("factory_info") or {}).get("parallel_groups") or [],
        "lanes": (twin.get("factory_info") or {}).get("lanes") or [],
        "stages": stages,
        "unassigned_workers": [
            worker_id for worker_id in worker_index
            if worker_id not in {str(item["worker_id"]) for item in positions}
        ],
        "bottlenecks": ((simulation or {}).get("live_simulation_state") or {}).get(
            "system_bottlenecks"
        ) or [],
        "alignment_report": report,
        "normalized_floor_state": normalized_floor,
    }