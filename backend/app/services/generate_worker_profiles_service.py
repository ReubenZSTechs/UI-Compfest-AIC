from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, Sequence

REQUIRED_DEMOGRAPHIC_KEYS = (
    "age",
    "gender",
    "years_of_experience",
    "baseline_physical_stamina",
    "cognitive_resilience",
)

REPAIR_TEMPLATE = (
    "PERBAIKAN\n"
    "Respons sebelumnya ditolak dengan alasan: {reason}. "
    "Ulangi untuk KANDIDAT yang sama, kembalikan tepat satu objek pada array workers, "
    "dan pastikan worker_id sama persis dengan yang diberikan."
)


class WorkerProfileCandidateError(RuntimeError):
    pass


class WorkerProfileGenerationError(RuntimeError):
    def __init__(self, message: str, failures: Sequence[dict[str, Any]]):
        super().__init__(message)
        self.failures = list(failures)


def candidate_solo_payload(candidate: Any, candidate_payload: Callable[[Any], str]) -> str:
    return f"Jumlah kandidat terbaca: 1\n\n{candidate_payload(candidate)}"


def validate_worker_entry(raw: Any, expected_worker_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("respons agent bukan objek JSON")

    workers = raw.get("workers")

    if not isinstance(workers, list) or len(workers) != 1:
        count = len(workers) if isinstance(workers, list) else "bukan array"
        raise ValueError(f"field workers harus berisi tepat 1 entri, didapat {count}")

    entry = workers[0]

    if not isinstance(entry, dict):
        raise ValueError("entri workers[0] bukan objek")

    worker_id = entry.get("worker_id")

    if worker_id != expected_worker_id:
        raise ValueError(
            f"worker_id tidak cocok: diminta '{expected_worker_id}', didapat '{worker_id}'"
        )

    demographics = entry.get("demographics")

    if not isinstance(demographics, dict):
        raise ValueError("demographics tidak ada atau bukan objek")

    missing = [key for key in REQUIRED_DEMOGRAPHIC_KEYS if key not in demographics]

    if missing:
        raise ValueError(f"demographics kekurangan field: {missing}")

    if not isinstance(entry.get("shift_context"), dict):
        raise ValueError("shift_context tidak ada atau bukan objek")

    return entry


def generate_one_profile(agent: Any, candidate: Any, candidate_payload: Callable[[Any], str],
                         max_attempts: int = 3, backoff_seconds: float = 1.5) -> dict[str, Any]:
    prompt = candidate_solo_payload(candidate, candidate_payload)
    last_reason: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        payload = prompt if last_reason is None else (
            f"{prompt}\n\n{REPAIR_TEMPLATE.format(reason=last_reason)}"
        )

        try:
            result = agent.generate_structured(user_prompt=payload)
            entry = validate_worker_entry(result, candidate.worker_id)
            return {"entry": entry, "attempts": attempt}

        except Exception as error:
            last_reason = f"{type(error).__name__}: {error}"

            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    raise WorkerProfileCandidateError(last_reason or "kegagalan tidak diketahui")


def generate_worker_profiles(document: Any, agent: Any, candidate_payload: Callable[[Any], str],
                             max_workers: int = 6, max_attempts: int = 3,
                             strict: bool = True,
                             progress: Optional[Callable[[int, int], None]] = None
                             ) -> dict[str, Any]:
    if agent is None:
        raise ValueError("Agent profil pekerja wajib disediakan.")

    candidates = list(document.candidates)

    if not candidates:
        raise ValueError("Tidak ada kandidat CV yang bisa diproses.")

    total = len(candidates)
    failures: list[dict[str, Any]] = []

    def run(candidate: Any) -> dict[str, Any]:
        try:
            outcome = generate_one_profile(
                agent, candidate, candidate_payload, max_attempts=max_attempts
            )
            return {"worker_id": candidate.worker_id, "outcome": outcome}

        except WorkerProfileCandidateError as error:
            return {
                "worker_id": candidate.worker_id,
                "source_name": candidate.source_name,
                "error": str(error),
            }

    results_by_id: dict[str, dict[str, Any]] = {}
    retries = 0

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        for done, outcome in enumerate(pool.map(run, candidates), start=1):
            if "outcome" in outcome:
                results_by_id[outcome["worker_id"]] = outcome["outcome"]
                retries += outcome["outcome"]["attempts"] - 1
            else:
                failures.append(outcome)

            if progress is not None:
                progress(done, total)

    if failures and strict:
        raise WorkerProfileGenerationError(
            f"{len(failures)} dari {total} kandidat gagal diproses agent.",
            failures,
        )

    ordered_workers = [
        results_by_id[candidate.worker_id]["entry"]
        for candidate in candidates
        if candidate.worker_id in results_by_id
    ]

    return {
        "workers": ordered_workers,
        "meta": {
            "candidate_count": total,
            "processed_count": len(ordered_workers),
            "failed_count": len(failures),
            "retries": retries,
            "failures": failures,
        },
    }