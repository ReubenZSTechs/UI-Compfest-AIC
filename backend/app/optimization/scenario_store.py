from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[2]
RL_ROOT = Path(os.getenv("RL_OUTPUT_DIR") or BACKEND_ROOT / "outputs" / "rl")
DEFAULT_FACTORY_DIR = "_default"


def rl_dir(factory_id: Optional[str]) -> Path:
    """Return the working directory that holds every RL artifact of one factory."""
    return RL_ROOT / (factory_id or DEFAULT_FACTORY_DIR)


def artifact_path(factory_id: Optional[str]) -> Path:
    """Return the path of the exported optimal_state.json for one factory."""
    return rl_dir(factory_id) / "optimal_state.json"


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON through a temporary file so readers never see a partial document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> Optional[Any]:
    """Read a JSON file, returning None when it is missing or unreadable."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_optimization_result(factory_id: Optional[str]) -> Optional[dict[str, Any]]:
    """Load the RL scenario bundle exported for a factory, if training has finished."""
    payload = read_json(artifact_path(factory_id))
    if not payload:
        return None
    bundle = payload.get("hasil_optimisasi_skenario_optimal")
    if bundle and bundle.get("scenarios"):
        return bundle
    return None
