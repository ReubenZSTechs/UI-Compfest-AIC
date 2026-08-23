from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from backend.app.services.call_llm_service import LLMOutputTruncatedError, AgentCallError
from backend.app.services.usage_metrics_service import clone_usage, merge_usage

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

ALWAYS_KEEP_TABLES = {4, 5}

TABLE_MARKER = re.compile(r"^\s*TABEL\s+(\d+)", re.IGNORECASE)
SEPARATOR_ROW = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")

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

REPAIR_DIRECTIVE = (
    "PERBAIKAN\n"
    "Respons sebelumnya ditolak: {reason}. Ulangi shard yang sama dengan cakupan identik."
)

LAST_RESORT_STRATEGIES = [
    {"repetition_penalty": 1.15, "concise": False},
    {"repetition_penalty": 1.3, "concise": True},
]

CONCISE_DIRECTIVE = (
    "\n\nPERINGATAN PANJANG TEKS\n"
    "Percobaan sebelumnya untuk entri ini gagal karena teks terlalu panjang atau "
    "mengulang kalimat yang sama berulang kali. Untuk percobaan ini, buat setiap field "
    "naratif (operator_task, qc_requirement, metric_derivation_reasoning, dan field teks "
    "bebas lainnya) maksimal SATU kalimat singkat dan padat. Dilarang mengulang kalimat "
    "atau frasa yang sama dua kali."
)

SCOPED_PAYLOAD_NOTE = (
    "CATATAN CAKUPAN\n"
    "Tabel di atas SUDAH DIPANGKAS dan hanya memuat baris milik shard ini. "
    "Seluruh tahap lain pada pabrik sengaja dihilangkan. Jangan mengarang tahap "
    "yang tidak muncul pada tabel ini, dan jangan memulai penomoran ulang dari tahap pertama."
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


def initial_tokens_for(task: ShardTask) -> int:
    base = SHARD_BASE_TOKENS.get(task.field, 800)

    if task.field not in SHARD_PER_ITEM_TOKENS:
        return base

    count = max(1, len(task.items))
    return base + SHARD_PER_ITEM_TOKENS[task.field] * count


PARENT_ATTEMPT_CEILING_CAP = 12000


def parent_ceiling_for(task: ShardTask) -> int:
    return min(initial_tokens_for(task) * 2, PARENT_ATTEMPT_CEILING_CAP)


def shard_schema(master: dict[str, Any], field: str, count: int | None) -> dict[str, Any]:
    node = master["properties"][field]

    if count is not None and node.get("type") == "array":
        node = {**node, "minItems": count, "maxItems": count}

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [field],
        "properties": {field: node},
    }

    if "$defs" in master:
        schema["$defs"] = master["$defs"]

    return schema


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

    return {
        "stage_ids": stage_ids,
        "asset_ids": asset_ids,
        "stage_names": list(stage_names),
        "stage_assets": dict(zip(stage_ids, asset_ids)),
    }


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
                "stage_names": [
                    stage.get("stage_name") or stage["stage_id"] for stage in stages
                ],
                "stage_assets": {
                    stage["stage_id"]: stage.get("asset_id")
                    for stage in stages
                    if stage.get("asset_id")
                },
            }

    if stage_names:
        return derive_canonical_scope(stage_names)

    outline = agent.generate_structured(
        user_prompt=f"{payload}\n\n{OUTLINE_DIRECTIVE}",
        schema_override=OUTLINE_SCHEMA,
    )

    derived_ids = [str(item) for item in outline.get("stage_ids") or []]
    derived_assets = [str(item) for item in outline.get("asset_ids") or []]

    return {
        "stage_ids": derived_ids,
        "asset_ids": derived_assets,
        "stage_names": None,
        "stage_assets": dict(zip(derived_ids, derived_assets)),
    }


def asset_for_stage(stage_id: str, scope: dict[str, Any]) -> str | None:
    mapping = scope.get("stage_assets") or {}

    if stage_id in mapping and mapping[stage_id]:
        return mapping[stage_id]

    stage_ids = scope.get("stage_ids") or []
    asset_ids = scope.get("asset_ids") or []

    if stage_id in stage_ids:
        index = stage_ids.index(stage_id)
        if index < len(asset_ids):
            return asset_ids[index]

    return None


def stage_for_asset(asset_id: str, scope: dict[str, Any]) -> str | None:
    for stage_id, mapped in (scope.get("stage_assets") or {}).items():
        if mapped == asset_id:
            return stage_id

    asset_ids = scope.get("asset_ids") or []
    stage_ids = scope.get("stage_ids") or []

    if asset_id in asset_ids:
        index = asset_ids.index(asset_id)
        if index < len(stage_ids):
            return stage_ids[index]

    return None


def stage_name_for(stage_id: str, scope: dict[str, Any]) -> str:
    stage_ids = scope.get("stage_ids") or []
    stage_names = scope.get("stage_names") or []

    if stage_id in stage_ids:
        index = stage_ids.index(stage_id)
        if index < len(stage_names):
            return stage_names[index] or ""

    return ""


def normalize_cell(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def shard_row_tokens(task: ShardTask, scope: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()

    for item in task.items:
        stage_id = stage_for_asset(item, scope) if task.field == "assets" else item
        asset_id = item if task.field == "assets" else asset_for_stage(item, scope)

        for value in (stage_id, asset_id):
            if value:
                tokens.add(normalize_cell(value))

        if stage_id:
            name = stage_name_for(stage_id, scope)
            if name:
                tokens.add(normalize_cell(name))

    for name in task.names:
        if name:
            tokens.add(normalize_cell(name))

    return {token for token in tokens if token}


ID_COLUMN_HEADERS = {
    "tahap_id", "aset_id", "alokasi_id", "tahap_proses", "tahap proses",
    "nama_peralatan", "peralatan",
}


def split_row(line: str) -> list[str]:
    return [normalize_cell(cell) for cell in line.strip().strip("|").split("|")]


def identifier_columns(header_line: str) -> set[int]:
    columns = {
        index for index, cell in enumerate(split_row(header_line))
        if cell in ID_COLUMN_HEADERS
    }
    return columns or {0}


def row_matches(line: str, tokens: set[str], columns: set[int]) -> bool:
    cells = split_row(line)
    return any(
        cells[index] in tokens
        for index in columns
        if index < len(cells) and cells[index]
    )


def build_scoped_payload(payload: str, task: ShardTask, scope: dict[str, Any]) -> str:
    tokens = shard_row_tokens(task, scope)

    if not tokens:
        return payload

    output: list[str] = []
    table_index: Optional[int] = None
    header_seen = False
    columns: set[int] = {0}
    kept_rows = 0
    saw_filtered_table = False

    for line in payload.splitlines():
        marker = TABLE_MARKER.match(line)

        if marker is not None:
            table_index = int(marker.group(1))
            header_seen = False
            output.append(line)
            continue

        if not line.strip().startswith("|"):
            output.append(line)
            continue

        if table_index is None or table_index in ALWAYS_KEEP_TABLES:
            output.append(line)
            continue

        saw_filtered_table = True

        if not header_seen:
            header_seen = True
            columns = identifier_columns(line)
            output.append(line)
            continue

        if SEPARATOR_ROW.match(line):
            output.append(line)
            continue

        if row_matches(line, tokens, columns):
            kept_rows += 1
            output.append(line)

    if not saw_filtered_table or kept_rows == 0:
        return payload

    return "\n".join(output) + "\n\n" + SCOPED_PAYLOAD_NOTE


def chunk_pairs(ids: Sequence[str], names: Sequence[str] | None, size: int):
    step = max(1, size)

    for start in range(0, len(ids), step):
        id_slice = tuple(ids[start:start + step])
        name_slice = tuple(names[start:start + step]) if names else None
        yield id_slice, name_slice


def build_tasks(scope: dict[str, Any],
                chunk_sizes: dict[str, int] | None = None) -> list[ShardTask]:
    sizes = {**DEFAULT_CHUNK_SIZES, **(chunk_sizes or {})}
    stage_ids = tuple(scope.get("stage_ids") or ())

    tasks = [
        ShardTask(
            shard_id=field,
            field=field,
            items=stage_ids if field == "factory_info" else (),
        )
        for field in SINGLETON_FIELDS
    ]

    for field in SCOPED_FIELDS:
        if field == "assets":
            source = list(scope.get("asset_ids") or [])
            names = [
                stage_name_for(stage_for_asset(item, scope) or "", scope)
                for item in source
            ]
        else:
            source = list(scope.get("stage_ids") or [])
            names = [stage_name_for(item, scope) for item in source]

        for index, (id_slice, name_slice) in enumerate(
            chunk_pairs(source, names, sizes[field]), start=1
        ):
            tasks.append(ShardTask(
                shard_id=f"{field}_{index:02d}",
                field=field,
                items=id_slice,
                names=tuple(name_slice or ()),
            ))

    return tasks


def canonicalize_entries(value: list[dict[str, Any]], task: ShardTask,
                         scope: dict[str, Any]) -> list[dict[str, Any]]:
    key = SCOPE_KEY[task.field]
    stage_ids = scope.get("stage_ids") or []
    canonical = []

    for index, entry in enumerate(value):
        entry = dict(entry)
        canonical_id = task.items[index]
        entry[key] = canonical_id

        if task.field == "process_stages":
            asset_id = asset_for_stage(canonical_id, scope)
            if asset_id:
                entry["asset_id"] = asset_id

        elif task.field == "job_descriptions":
            asset_id = asset_for_stage(canonical_id, scope)
            if asset_id:
                entry["assigned_asset_id"] = asset_id

            if canonical_id in stage_ids:
                entry["job_id"] = f"job-{stage_ids.index(canonical_id) + 1:02d}"

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

    if len(observed) != len(task.items):
        raise ValueError(
            f"jumlah entri tidak cocok: diminta {len(task.items)}, didapat {len(observed)}"
        )

    if observed != list(task.items):
        raise ValueError(
            f"{key} tidak cocok: diminta {list(task.items)}, didapat {observed}"
        )

    return value


def build_directive(task: ShardTask) -> str:
    is_singleton = task.field in SINGLETON_FIELDS

    if is_singleton and task.items:
        stage_list = "\n".join(
            f"{index + 1}. {stage_id}" for index, stage_id in enumerate(task.items)
        )
        return (
            "FASE 2 - SHARD\n"
            f"Kembalikan HANYA field '{task.field}'.\n"
            "Daftar stage_id kanonis berikut WAJIB dipakai persis, dalam urutan ini, "
            "untuk workflow_sequence dan setiap referensi tahap lain pada factory_info "
            "(termasuk lanes dan parallel_groups jika ada). Dilarang memakai nama tahap "
            "mentah atau id buatan sendiri:\n"
            f"{stage_list}"
        )

    if is_singleton:
        return (
            f"FASE 2 - SHARD\nKembalikan HANYA field '{task.field}'. "
            "Field lain dilarang muncul."
        )

    key = SCOPE_KEY[task.field]
    usable_names = [name for name in task.names if name]

    if len(usable_names) == len(task.items):
        pairing = "\n".join(
            f"- {identifier}  (nama tahap sumber: {name})"
            for identifier, name in zip(task.items, task.names)
        )
    else:
        pairing = "\n".join(f"- {identifier}" for identifier in task.items)

    return (
        "FASE 2 - SHARD\n"
        f"Kembalikan HANYA field '{task.field}'. Field lain dilarang muncul.\n"
        f"Hasilkan tepat {len(task.items)} entri, satu per baris berikut, dalam urutan "
        f"yang sama. WAJIB gunakan {key} PERSIS seperti tercantum di sini — dilarang "
        "membuat ulang penomoran, slug, atau id baru:\n"
        f"{pairing}\n\n"
        f"PENTING: entri pertama WAJIB memakai {key}='{task.items[0]}'. "
        "Tabel pada payload sudah dipangkas hanya untuk shard ini, sehingga tidak ada "
        "tahap lain yang boleh dihasilkan."
    )


def build_concise_directive(task: ShardTask) -> str:
    return CONCISE_DIRECTIVE


def run_shard(agent: Any, master_schema: dict[str, Any], payload: str, task: ShardTask,
              max_attempts: int, backoff_seconds: float,
              min_split_size: int = 1, deadline: float | None = None,
              *, scope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(max_attempts, int):
        raise TypeError(
            f"run_shard('{task.shard_id}'): max_attempts bukan int, didapat "
            f"{type(max_attempts).__name__}: {max_attempts!r}."
        )

    if deadline is not None and time.monotonic() >= deadline:
        return {
            "shard_id": task.shard_id,
            "field": task.field,
            "error": "Anggaran waktu shard habis sebelum sempat dicoba.",
        }

    is_singleton = task.field in SINGLETON_FIELDS
    count = None if is_singleton else (len(task.items) or None)
    schema = shard_schema(master_schema, task.field, count)

    scoped_payload = payload if is_singleton else build_scoped_payload(payload, task, scope)
    prompt = f"{scoped_payload}\n\n{build_directive(task)}"

    reason: Optional[str] = None
    oversized = False

    for attempt in range(1, max_attempts + 1):
        if deadline is not None and time.monotonic() >= deadline:
            reason = reason or "Anggaran waktu shard habis di tengah percobaan."
            break

        request = prompt if reason is None else (
            f"{prompt}\n\n{REPAIR_DIRECTIVE.format(reason=reason)}"
        )

        try:
            raw = agent.generate_structured(
                user_prompt=request,
                schema_override=schema,
                initial_max_tokens=min(initial_tokens_for(task), parent_ceiling_for(task)),
                max_tokens_ceiling=parent_ceiling_for(task),
                enable_last_resort=False,
            )
            usage = clone_usage(agent.last_usage)
            value = validate_shard(raw, task)

            if task.field in SCOPE_KEY:
                value = canonicalize_entries(value, task, scope)

            return {
                "shard_id": task.shard_id,
                "field": task.field,
                "value": value,
                "usage": usage,
                "attempts": attempt,
            }

        except (LLMOutputTruncatedError, AgentCallError) as error:
            oversized = True
            reason = str(error)

            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

        except Exception as error:
            reason = f"{type(error).__name__}: {error}"

            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    can_split = (not is_singleton) and task.items and len(task.items) > min_split_size
    time_left = deadline is None or time.monotonic() < deadline

    if can_split and time_left:
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

        if failed is None:
            return {
                "shard_id": task.shard_id,
                "field": task.field,
                "value": [entry for item in sub_results for entry in item["value"]],
                "usage": merge_usage([item["usage"] for item in sub_results]),
                "attempts": sum(item["attempts"] for item in sub_results),
            }

        return {
            "shard_id": task.shard_id,
            "field": task.field,
            "error": f"[pecah -> {failed['shard_id']}] {failed['error']}",
        }

    if oversized and time_left:
        last_resort_tokens = max(initial_tokens_for(task) * 2, 4000)

        for strategy_index, strategy in enumerate(LAST_RESORT_STRATEGIES, start=1):
            if deadline is not None and time.monotonic() >= deadline:
                break

            last_resort_prompt = prompt + (
                build_concise_directive(task) if strategy["concise"] else ""
            )

            try:
                raw = agent.generate_structured(
                    user_prompt=last_resort_prompt,
                    schema_override=schema,
                    initial_max_tokens=last_resort_tokens,
                    extra_args={"repetition_penalty": strategy["repetition_penalty"]},
                    enable_last_resort=False,
                )
                usage = clone_usage(agent.last_usage)
                value = validate_shard(raw, task)

                if task.field in SCOPE_KEY:
                    value = canonicalize_entries(value, task, scope)

                return {
                    "shard_id": task.shard_id,
                    "field": task.field,
                    "value": value,
                    "usage": usage,
                    "attempts": max_attempts + strategy_index,
                }

            except Exception as error:
                reason = (
                    f"{reason} | percobaan darurat #{strategy_index} "
                    f"(repetition_penalty={strategy['repetition_penalty']}, "
                    f"ringkas={strategy['concise']}) juga gagal: "
                    f"{type(error).__name__}: {error}"
                )

    if oversized:
        if is_singleton:
            reason = (
                f"Field '{task.field}' tetap gagal walau max_tokens sudah dinaikkan dan "
                f"seluruh strategi darurat sudah dicoba. Field ini bukan daftar sehingga "
                f"tidak bisa dipecah lebih lanjut. {reason}"
            )
        elif not can_split:
            target = task.items[0] if task.items else task.field
            reason = (
                f"'{target}' tetap gagal pada satu entri tunggal walau sudah dicoba "
                f"{len(LAST_RESORT_STRATEGIES)} strategi darurat. {reason}"
            )

    return {"shard_id": task.shard_id, "field": task.field, "error": reason}


def merge_results(results: Sequence[dict[str, Any]], scope: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    for field in SINGLETON_FIELDS:
        for result in results:
            if result["field"] == field:
                merged[field] = result["value"]

    for field in SCOPED_FIELDS:
        blocks = sorted(
            (result for result in results if result["field"] == field),
            key=lambda item: item["shard_id"],
        )

        key = SCOPE_KEY[field]
        seen: set[str] = set()
        entries: list[dict[str, Any]] = []

        for block in blocks:
            for entry in block["value"]:
                identifier = str(entry.get(key))

                if identifier in seen:
                    continue

                seen.add(identifier)
                entries.append(entry)

        order = scope["asset_ids"] if field == "assets" else scope["stage_ids"]
        position = {identifier: index for index, identifier in enumerate(order)}
        entries.sort(key=lambda item: position.get(str(item.get(key)), 10 ** 6))

        merged[field] = entries

    return merged


def apply_canonical_sequence(factory: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    stage_ids = scope.get("stage_ids") or []

    if not stage_ids:
        return factory

    info = dict(factory.get("factory_info") or {})
    info["workflow_sequence"] = list(stage_ids)
    factory["factory_info"] = info

    canonical = set(stage_ids)
    position = {stage_id: index for index, stage_id in enumerate(stage_ids)}

    for stage in factory.get("process_stages") or []:
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


def missing_entities(factory: dict[str, Any], scope: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []

    for field in SCOPED_FIELDS:
        key = SCOPE_KEY[field]
        expected = scope["asset_ids"] if field == "assets" else scope["stage_ids"]
        present = {str(entry.get(key)) for entry in factory.get(field) or []}

        for identifier in expected:
            if identifier not in present:
                problems.append({
                    "entitas": identifier,
                    "masalah": f"tidak ada entri pada {field}",
                })

    return problems


def cross_reference_problems(factory: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    stages = {str(stage.get("stage_id")): stage for stage in factory.get("process_stages") or []}
    assets = {str(asset.get("asset_id")) for asset in factory.get("assets") or []}

    for stage_id, stage in stages.items():
        asset_id = str(stage.get("asset_id") or "")

        if asset_id not in assets:
            problems.append({
                "entitas": stage_id,
                "masalah": f"asset_id '{asset_id}' tidak ada di assets",
            })

        next_stage_id = stage.get("next_stage_id")

        if not stage.get("is_terminal") and str(next_stage_id or "") not in stages:
            problems.append({
                "entitas": stage_id,
                "masalah": f"next_stage_id '{next_stage_id}' tidak dikenal",
            })

    for job in factory.get("job_descriptions") or []:
        job_id = str(job.get("job_id") or job.get("allocation_id") or "?")
        stage_id = str(job.get("stage_id") or job.get("workflow_step") or "")

        if stage_id not in stages:
            problems.append({
                "entitas": job_id,
                "masalah": f"stage_id '{stage_id}' tidak ada di process_stages",
            })

        asset_id = str(job.get("assigned_asset_id") or "")

        if asset_id and asset_id not in assets:
            problems.append({
                "entitas": job_id,
                "masalah": f"assigned_asset_id '{asset_id}' tidak ada di assets",
            })

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

    factory = merge_results(results, scope)
    factory = apply_canonical_sequence(factory, scope)
    elapsed = time.perf_counter() - started

    factory["meta"] = {
        "shard_count": total,
        "shard_failed": len(failures),
        "retries": sum(result["attempts"] - 1 for result in results),
        "elapsed_seconds": round(elapsed, 2),
        "usage": merge_usage([result["usage"] for result in results]),
        "failures": failures,
        "missing_entities": missing_entities(factory, scope),
        "cross_reference_problems": cross_reference_problems(factory),
        "scope": scope,
    }

    return factory