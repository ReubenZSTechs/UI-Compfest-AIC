from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

SCENARIO_ROOT = Path("outputs/rl")
FALLBACK_ARTIFACT = Path("training/outputs/optimal_state.json")


def artifact_path(factory_id: Optional[str]) -> Path:
    if factory_id:
        return SCENARIO_ROOT / factory_id / "optimal_state.json"
    return FALLBACK_ARTIFACT


def load_optimization_result(factory_id: Optional[str]) -> Optional[dict[str, Any]]:
    candidates = [artifact_path(factory_id)]
    if factory_id:
        candidates.append(FALLBACK_ARTIFACT)

    for path in candidates:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        bundle = payload.get("hasil_optimisasi_skenario_optimal")
        if bundle and bundle.get("scenarios"):
            return bundle

    return None