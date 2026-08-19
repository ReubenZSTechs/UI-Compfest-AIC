from __future__ import annotations

import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence
from openai import APITimeoutError

from backend.app.services.usage_metrics_service import (
    clone_usage,
    merge_usage
)

from backend.app.services.call_llm_service import LLMOutputTruncatedError

SCOPED_FIELDS = ("process_stages", "assets", "job_descriptions")
SINGLETON_FIELDS = ("factory_info", "shifts")

SCOPE_KEY = {
    "process_stages": "stage_id",
    "assets": "asset_id",
    "job_descriptions": "stage_id",
}

DEFAULT_CHUNK_SIZES = {
    "process_stages": 3,
    "assets": 4,
    "job_descriptions": 4,
}

OUTLINE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["stage_ids", "asset_ids"],
    "properties": {
        "stage_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "asset_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
    },
}

OUTLINE_DIRECTIVE = (
    "FASE 1 - KERANGKA\n"
    "Kembalikan HANYA daftar id, tanpa detail apa pun.\n"
    "stage_ids: seluruh Tahap_ID pada TABEL 1, urut topologis.\n"
    "asset_ids: seluruh Aset_ID pada TABEL 3, urut mengikuti stage_ids.\n"
    "Jangan membuat id baru yang tidak ada pada tabel sumber."
)

SHARD_DIRECTIVE = (
    "FASE 2 - SHARD\n"
    "Kembalikan HANYA field '{field}'. Field lain dilarang muncul.\n"
    "Cakupan shard ini: {scope}.\n"
    "Hasilkan tepat {count} entri, berurutan persis seperti cakupan di atas, "
    "dengan {key} yang sama persis. Jangan menambah, menggabungkan, atau melewati entri."
)

REPAIR_DIRECTIVE = (
    "PERBAIKAN\n"
    "Respons sebelumnya ditolak: {reason}. Ulangi shard yang sama dengan cakupan identik."
)

SHARD_BASE_TOKENS = {
    "process_stages": 300,
    "assets": 300,
    "job_descriptions": 300,
    "factory_info": 2600,
    "shifts": 500,
}

SHARD_PER_ITEM_TOKENS = {
    "process_stages": 1700,
    "assets": 1100,
    "job_descriptions": 1100,
}


def initial_tokens_for(task: ShardTask) -> int:
    base = SHARD_BASE_TOKENS.get(task.field, 800)

    if task.field not in SHARD_PER_ITEM_TOKENS:
        result = base
    else:
        count = max(1, len(task.items))
        result = base + SHARD_PER_ITEM_TOKENS[task.field] * count

    if not isinstance(result, int):
        raise TypeError(
            f"initial_tokens_for('{task.field}') menghasilkan {type(result).__name__}, "
            f"bukan int: {result!r}"
        )

    return result


class ShardGenerationError(RuntimeError):
    def __init__(self, message: str, failures: Sequence[dict[str, Any]]):
        super().__init__(message)
        self.failures = list(failures)


@dataclass(frozen=True)
class ShardTask:
    shard_id: str
    field: str
    items: tuple[str, ...]
    names: tuple[str, ...] = ()


def clone_usage(usage: Any) -> dict[str, int]:
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def merge_usage(entries: Sequence[dict[str, int]]) -> dict[str, int]:
    return {
        key: sum(entry.get(key, 0) for entry in entries)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def collect_refs(node: Any, defs: dict[str, Any], seen: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.removeprefix("#/$defs/")
            if name not in seen and name in defs:
                seen.add(name)
                collect_refs(defs[name], defs, seen)
        for value in node.values():
            collect_refs(value, defs, seen)
    elif isinstance(node, list):
        for item in node:
            collect_refs(item, defs, seen)


def shard_schema(master: dict[str, Any], field: str, count: int | None) -> dict[str, Any]:
    node = master["properties"][field]

    if count is not None and node.get("type") == "array":
        node = {**node, "minItems": count, "maxItems": count}

    schema = {
        "type": "object", "additionalProperties": False,
        "required": [field], "properties": {field: node},
    }

    defs = master.get("$defs")
    if defs:
        seen: set[str] = set()
        collect_refs(node, defs, seen)
        if seen:
            schema["$defs"] = {name: defs[name] for name in seen}

    return schema


def chunk(items: Sequence[str], size: int) -> list[tuple[str, ...]]:
    step = max(1, size)
    return [tuple(items[index:index + step]) for index in range(0, len(items), step)]


def chunk_pairs(ids: Sequence[str], names: Sequence[str] | None, size: int):
    step = max(1, size)
    for start in range(0, len(ids), step):
        id_slice = tuple(ids[start:start + step])
        name_slice = tuple(names[start:start + step]) if names else None
        yield id_slice, name_slice


def build_tasks(scope: dict[str, Any], chunk_sizes: dict[str, int] | None = None) -> list[ShardTask]:
    sizes = {**DEFAULT_CHUNK_SIZES, **(chunk_sizes or {})}
    stage_ids = tuple(scope.get("stage_ids") or ())

    tasks = [
        ShardTask(
            shard_id=field, field=field,
            items=stage_ids if field == "factory_info" else (),
        )
        for field in SINGLETON_FIELDS
    ]

    stage_names = scope.get("stage_names")

    for field in SCOPED_FIELDS:
        source = scope["asset_ids"] if field == "assets" else scope["stage_ids"]
        names = stage_names if field != "assets" else None

        for index, (id_slice, name_slice) in enumerate(
            chunk_pairs(source, names, sizes[field]), start=1
        ):
            tasks.append(ShardTask(
                shard_id=f"{field}_{index:02d}",
                field=field,
                items=id_slice,
                names=name_slice or (),
            ))

    return tasks


def build_scope(agent: Any, payload: str,
                workbook: dict[str, Any] | None = None,
                stage_names: Sequence[str] | None = None) -> dict[str, Any]:
    if workbook:
        stages = workbook.get("stages") or []
        stage_ids = [stage["stage_id"] for stage in stages]
        asset_ids = [asset["asset_id"] for asset in workbook.get("assets") or []]

        if stage_ids and asset_ids:
            return {
                "stage_ids": stage_ids,
                "asset_ids": asset_ids,
                "stage_names": [stage.get("stage_name") or stage["stage_id"] for stage in stages],
            }

    if stage_names:
        return derive_canonical_scope(stage_names)

    outline = agent.generate_structured(
        user_prompt=f"{payload}\n\n{OUTLINE_DIRECTIVE}",
        schema_override=OUTLINE_SCHEMA,
    )

    return {
        "stage_ids": [str(item) for item in outline.get("stage_ids") or []],
        "asset_ids": [str(item) for item in outline.get("asset_ids") or []],
        "stage_names": None,
    }


def apply_canonical_sequence(factory: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    stage_ids = scope.get("stage_ids") or []

    if not stage_ids:
        return factory

    info = dict(factory.get("factory_info") or {})
    info["workflow_sequence"] = list(stage_ids)
    factory["factory_info"] = info

    canonical = set(stage_ids)
    position = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    stages = factory.get("process_stages") or []

    for stage in stages:
        index = position.get(stage.get("stage_id"))

        if index is None:
            continue

        next_id = stage.get("next_stage_id")
        is_terminal = bool(stage.get("is_terminal"))

        if is_terminal and next_id in (None, ""):
            continue

        if not is_terminal and next_id in canonical:
            continue

        fallback_terminal = index == len(stage_ids) - 1
        stage["is_terminal"] = fallback_terminal
        stage["next_stage_id"] = None if fallback_terminal else stage_ids[index + 1]

    return factory


def canonicalize_entries(value: list[dict[str, Any]], task: ShardTask,
                         scope: dict[str, Any]) -> list[dict[str, Any]]:
    key = SCOPE_KEY[task.field]
    canonical = []

    for index, entry in enumerate(value):
        entry = dict(entry)
        canonical_id = task.items[index]
        entry[key] = canonical_id

        if task.field in ("process_stages", "job_descriptions"):
            global_index = scope["stage_ids"].index(canonical_id)
            asset_field = "asset_id" if task.field == "process_stages" else "assigned_asset_id"
            entry[asset_field] = scope["asset_ids"][global_index]

            if task.field == "job_descriptions":
                entry["job_id"] = f"job-{global_index + 1:02d}"

        canonical.append(entry)

    return canonical


def validate_shard(result: Any, task: ShardTask) -> Any:
    if not isinstance(result, dict):
        raise ValueError("respons shard bukan objek JSON")

    if task.field not in result:
        raise ValueError(f"field '{task.field}' tidak ada pada respons")

    value = result[task.field]

    if task.field in SINGLETON_FIELDS:
        return value

    if not isinstance(value, list):
        raise ValueError(f"field '{task.field}' bukan array")

    key = SCOPE_KEY[task.field]
    observed = [str(entry.get(key)) for entry in value if isinstance(entry, dict)]

    if observed != list(task.items):
        raise ValueError(
            f"{key} tidak cocok: diminta {list(task.items)}, didapat {observed}"
        )

    return value


def run_shard(agent: Any, master_schema: dict[str, Any], payload: str, task: ShardTask,
              max_attempts: int, backoff_seconds: float,
              min_split_size: int = 1, deadline: float | None = None,
              *, scope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(max_attempts, int):
        raise TypeError(
            f"run_shard('{task.shard_id}'): max_attempts bukan int, didapat "
            f"{type(max_attempts).__name__}: {max_attempts!r}. Periksa argumen di titik "
            f"pemanggilan run_shard — kemungkinan pergeseran posisi argumen."
        )

    if deadline is not None and time.monotonic() >= deadline:
        return {
            "shard_id": task.shard_id, "field": task.field,
            "error": "Anggaran waktu shard habis sebelum sempat dicoba.",
        }

    is_singleton = task.field in SINGLETON_FIELDS
    count = None if is_singleton else (len(task.items) or None)
    schema = shard_schema(master_schema, task.field, count)

    if is_singleton:
        if task.items:
            stage_list = "\n".join(
                f"{index + 1}. {stage_id}" for index, stage_id in enumerate(task.items)
            )
            directive = (
                "FASE 2 - SHARD\n"
                f"Kembalikan HANYA field '{task.field}'.\n"
                "Daftar stage_id kanonis berikut WAJIB dipakai persis, dalam urutan ini, "
                "untuk workflow_sequence dan setiap referensi tahap lain pada factory_info "
                "(termasuk lanes dan parallel_groups jika ada). Dilarang memakai nama tahap "
                "mentah atau id buatan sendiri:\n"
                f"{stage_list}"
            )
        else:
            directive = (
                f"FASE 2 - SHARD\nKembalikan HANYA field '{task.field}'. "
                "Field lain dilarang muncul."
            )
    elif task.names:
        pairing = "\n".join(
            f"- {stage_id}  (nama tahap sumber: {name})"
            for stage_id, name in zip(task.items, task.names)
        )
        directive = (
            "FASE 2 - SHARD\n"
            f"Kembalikan HANYA field '{task.field}'. Field lain dilarang muncul.\n"
            f"Hasilkan tepat {len(task.items)} entri, satu per baris berikut, dalam urutan "
            f"yang sama. WAJIB gunakan {SCOPE_KEY[task.field]} PERSIS seperti tercantum di "
            "sini — dilarang membuat ulang penomoran, slug, atau id baru:\n"
            f"{pairing}"
        )
    elif task.items:
        directive = SHARD_DIRECTIVE.format(
            field=task.field, scope=", ".join(task.items),
            count=len(task.items), key=SCOPE_KEY[task.field],
        )
    else:
        directive = (
            f"FASE 2 - SHARD\nKembalikan HANYA field '{task.field}'. "
            "Field lain dilarang muncul."
        )

    prompt = f"{payload}\n\n{directive}"
    reason: Optional[str] = None
    oversized = False

    for attempt in range(1, max_attempts + 1):
        if deadline is not None and time.monotonic() >= deadline:
            reason = reason or "Anggaran waktu shard habis di tengah percobaan."
            break

        request = prompt if reason is None else f"{prompt}\n\n{REPAIR_DIRECTIVE.format(reason=reason)}"

        try:
            raw = agent.generate_structured(
                user_prompt=request, schema_override=schema,
                initial_max_tokens=initial_tokens_for(task),
            )
            usage = clone_usage(agent.last_usage)
            value = validate_shard(raw, task)

            if task.field in SCOPE_KEY:
                value = canonicalize_entries(value, task, scope)

            return {
                "shard_id": task.shard_id, "field": task.field,
                "value": value, "usage": usage, "attempts": attempt,
            }

        except (LLMOutputTruncatedError, APITimeoutError) as error:
            oversized = True
            reason = str(error)
            break

        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    can_split = (not is_singleton) and task.items and len(task.items) > min_split_size
    time_left = deadline is None or time.monotonic() < deadline

    if oversized and can_split and time_left:
        midpoint = len(task.items) // 2
        halves = (
            ShardTask(f"{task.shard_id}a", task.field,
                     task.items[:midpoint], task.names[:midpoint]),
            ShardTask(f"{task.shard_id}b", task.field,
                     task.items[midpoint:], task.names[midpoint:]),
        )

        sub_results = [
            run_shard(
                agent=agent, master_schema=master_schema, payload=payload, task=half,
                max_attempts=max_attempts, backoff_seconds=backoff_seconds,
                min_split_size=min_split_size, deadline=deadline, scope=scope,
            )
            for half in halves
        ]

        failed = next((item for item in sub_results if "error" in item), None)
        if failed is not None:
            return {
                "shard_id": task.shard_id, "field": task.field,
                "error": f"[pecah -> {failed['shard_id']}] {failed['error']}",
            }

        return {
            "shard_id": task.shard_id, "field": task.field,
            "value": [entry for item in sub_results for entry in item["value"]],
            "usage": merge_usage([item["usage"] for item in sub_results]),
            "attempts": sum(item["attempts"] for item in sub_results),
        }

    if oversized and time_left:
        try:
            raw = agent.generate_structured(
                user_prompt=prompt, schema_override=schema,
                initial_max_tokens=initial_tokens_for(task),
                extra_args={"repetition_penalty": 1.15},
            )
            usage = clone_usage(agent.last_usage)
            return {
                "shard_id": task.shard_id, "field": task.field,
                "value": validate_shard(raw, task), "usage": usage, "attempts": max_attempts + 1,
            }
        except Exception as error:
            reason = f"{reason} | percobaan dengan repetition_penalty juga gagal: {type(error).__name__}: {error}"

    if oversized:
        if is_singleton:
            reason = (
                f"Field '{task.field}' tetap terpotong walau sudah dinaikkan max_tokens dan "
                "dicoba dengan repetition_penalty. Field ini bukan daftar sehingga tidak bisa "
                "dipecah lebih lanjut."
            )
        elif not can_split:
            target = task.items[0] if task.items else task.field
            reason = (
                f"'{target}' tetap terpotong pada satu entri tunggal walau sudah dicoba dengan "
                f"repetition_penalty. {reason}"
            )
        else:
            reason = f"{reason} — anggaran waktu shard habis sebelum sempat memecah lebih lanjut."

    return {"shard_id": task.shard_id, "field": task.field, "error": reason}


def slugify_stage_name(name: str) -> str:
    text = str(name or "").strip().lower()
    text = text.replace("&", " dan ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "tahap"


def derive_canonical_scope(stage_names: Sequence[str]) -> dict[str, Any]:
    stage_ids = [
        f"step_{index:02d}_{slugify_stage_name(name)}"
        for index, name in enumerate(stage_names, start=1)
    ]
    asset_ids = [f"ast-{index:02d}" for index in range(1, len(stage_names) + 1)]

    return {"stage_ids": stage_ids, "asset_ids": asset_ids, "stage_names": list(stage_names)}


def merge_results(results: Sequence[dict[str, Any]], scope: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    for field in SINGLETON_FIELDS:
        for result in results:
            if result["field"] == field:
                merged[field] = result["value"]

    for field in SCOPED_FIELDS:
        blocks = [result for result in results if result["field"] == field]
        blocks.sort(key=lambda item: item["shard_id"])

        key = SCOPE_KEY[field]
        seen: set[str] = set()
        entries = []

        for block in blocks:
            for entry in block["value"]:
                identifier = str(entry.get(key))
                if identifier in seen:
                    continue
                seen.add(identifier)
                entries.append(entry)

        order = scope["asset_ids"] if field == "assets" else scope["stage_ids"]
        position = {identifier: index for index, identifier in enumerate(order)}
        entries.sort(key=lambda item: position.get(str(item.get(key)), 10**6))

        merged[field] = entries

    return merged


def cross_reference_problems(factory: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    stages = {str(stage.get("stage_id")): stage for stage in factory.get("process_stages") or []}
    assets = {str(asset.get("asset_id")) for asset in factory.get("assets") or []}

    for stage_id, stage in stages.items():
        asset_id = str(stage.get("asset_id") or "")

        if asset_id not in assets:
            problems.append({"entitas": stage_id, "masalah": f"asset_id '{asset_id}' tidak ada di assets"})

        next_stage_id = stage.get("next_stage_id")

        if not stage.get("is_terminal") and str(next_stage_id or "") not in stages:
            problems.append({"entitas": stage_id, "masalah": f"next_stage_id '{next_stage_id}' tidak dikenal"})

    for job in factory.get("job_descriptions") or []:
        job_id = str(job.get("job_id") or job.get("allocation_id") or "?")
        stage_id = str(job.get("stage_id") or job.get("workflow_step") or "")

        if stage_id not in stages:
            problems.append({"entitas": job_id, "masalah": f"stage_id '{stage_id}' tidak ada di process_stages"})

        asset_id = str(job.get("assigned_asset_id") or "")

        if asset_id and asset_id not in assets:
            problems.append({"entitas": job_id, "masalah": f"assigned_asset_id '{asset_id}' tidak ada di assets"})

    return problems


def generate_factory_structure(agent: Any, master_schema: dict[str, Any], payload: str,
                               workbook: dict[str, Any] | None = None,
                               stage_names: Sequence[str] | None = None,
                               chunk_sizes: dict[str, int] | None = None,
                               max_workers: int = 8, max_attempts: int = 3,
                               backoff_seconds: float = 1.5, strict: bool = False,
                               shard_timeout_seconds: float = 480.0,
                               progress: Optional[Callable[[int, int, list[str]], None]] = None
                               ) -> dict[str, Any]:
    if agent is None:
        raise ValueError("Agent struktur pabrik wajib disediakan.")

    started = time.perf_counter()
    scope = build_scope(agent, payload, workbook, stage_names)

    if not scope["stage_ids"]:
        raise ValueError("Kerangka tahapan kosong; payload tidak memuat TABEL 1 yang terbaca.")

    tasks = build_tasks(scope, chunk_sizes)
    total = len(tasks)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    pending = {task.shard_id for task in tasks}

    def execute(task: ShardTask) -> dict[str, Any]:
        deadline = time.monotonic() + shard_timeout_seconds
        return run_shard(
            agent=agent, master_schema=master_schema, payload=payload, task=task,
            max_attempts=max_attempts, backoff_seconds=backoff_seconds,
            deadline=deadline, scope=scope,
        )

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(execute, task): task for task in tasks}
        done_count = 0

        for future in as_completed(futures):
            task = futures[future]
            result = future.result()
            pending.discard(task.shard_id)
            done_count += 1

            if "error" in result:
                failures.append(result)
            else:
                results.append(result)

            if progress is not None:
                progress(done_count, total, sorted(pending))

    if failures and strict:
        raise ShardGenerationError(f"{len(failures)} dari {total} shard gagal.", failures)

    factory = merge_results(results)
    factory = apply_canonical_sequence(factory, scope)
    elapsed = time.perf_counter() - started

    for result in results:
        if not isinstance(result.get("attempts"), int):
            raise TypeError(
                f"Shard {result.get('shard_id')}: field 'attempts' bukan int, "
                f"didapat {type(result.get('attempts')).__name__}: {result.get('attempts')!r}"
            )

    factory["meta"] = {
        "shard_count": total, "shard_failed": len(failures),
        "retries": sum(result["attempts"] - 1 for result in results),
        "elapsed_seconds": round(elapsed, 2),
        "usage": merge_usage([result["usage"] for result in results]),
        "failures": failures, "cross_reference_problems": cross_reference_problems(factory),
        "scope": scope,
    }

    return factory