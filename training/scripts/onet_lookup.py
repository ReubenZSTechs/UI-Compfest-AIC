"""
onet_lookup.py

Thin lookup layer over the downloaded O*NET database files (abilities.json,
work_context.json, job_zones.json, occupation_data.json) under
training/datasets/raw/onetdatabase/.

WHY hand-mapped SOC codes instead of fuzzy title matching: generate_synthetic_
factories.py only ever produces 8 fixed job titles (JOB_TITLE_TEMPLATES), so a
one-time manual mapping to a representative O*NET-SOC code per step is more
reliable and auditable than a similarity search over ~1000 occupations at
generation time. If you add new STEP_POOL entries later, add a matching entry
to STEP_TO_SOC below.

ASSUMED JSON KEYS (O*NET's standard flat-file column names). If your
conversion script used different keys, update _KEY_* below - everything else
is written against these constants so it's a one-line fix.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ONET_DIR = Path("./training/datasets/raw/onetdatabase/")

# --------------------------------------------------------------------------
# Column-name constants - adjust these if your JSON export used different
# headers than O*NET's raw flat files.
# --------------------------------------------------------------------------
_KEY_SOC = "onetsoc_code"
_KEY_ELEMENT_NAME = "element_name"
_KEY_SCALE_ID = "scale_id"
_KEY_DATA_VALUE = "data_value"
_KEY_JOB_ZONE = "job_zone"
_KEY_TITLE = "title"

# --------------------------------------------------------------------------
# Step -> representative O*NET-SOC code. Picked by hand for the 8 templates
# in generate_synthetic_factories.py's STEP_POOL / JOB_TITLE_TEMPLATES.
# --------------------------------------------------------------------------
STEP_TO_SOC = {
    "Raw Material Intake": "53-7062.00",   # Laborers and Freight, Stock, and Material Movers, Hand
    "Cutting": "51-9031.00",               # Cutters and Trimmers, Hand
    "Machining": "51-4041.00",             # Machinists
    "Assembly": "51-2092.00",              # Team Assemblers
    "Surface Treatment": "51-9021.00",     # Coating, Painting, and Spraying Machine Setters/Operators
    "Quality Inspection": "51-9061.00",    # Inspectors, Testers, Sorters, Samplers, and Weighers
    "Packaging": "51-9111.00",             # Packaging and Filling Machine Operators and Tenders
    "Palletizing": "53-7062.00",           # same as material moving - no dedicated SOC code
}

# Abilities.txt "Element Name" values used for each derived metric.
# LV (Level) scale runs 0-7 in the raw data; we normalize to 0-1 by /7.
PHYSICAL_ABILITY_ELEMENTS = ["Static Strength", "Dynamic Strength", "Stamina", "Trunk Strength"]
COGNITIVE_ABILITY_ELEMENTS = ["Selective Attention", "Perceptual Speed", "Reaction Time", "Problem Sensitivity"]
FOCUS_ABILITY_ELEMENTS = ["Selective Attention", "Perceptual Speed"]

# Work Context "Element Name" used for error_severity bucketing (CX scale, 1-5)
ERROR_CONTEXT_ELEMENT = "Consequence of Error"


def _load_json(filename: str) -> list:
    path = ONET_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Expected O*NET file at {path} - check ONET_DIR / that the download landed there."
        )
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # this O*NET export wraps the record list in a {"row": [...]} envelope
    # (confirmed against abilities.json/job_zones.json/work_context.json) -
    # unwrap it, but fall back to treating raw as the list directly in case
    # a future/different export drops the wrapper.
    if isinstance(raw, dict) and "row" in raw:
        return raw["row"]
    if isinstance(raw, list):
        return raw
    raise ValueError(
        f"{filename}: unrecognized top-level JSON shape ({type(raw).__name__}). "
        f"Expected a list or a dict with a 'row' key."
    )


class OnetProfiles:
    """Loads all four O*NET files once and exposes per-SOC-code lookups.
    Instantiate a single OnetProfiles() at the top of generate_synthetic_
    factories.py's main() and reuse it across all 101 factories - re-parsing
    the JSON files per-factory would be wasteful."""

    def __init__(self, onet_dir: Path = None):
        global ONET_DIR
        if onet_dir:
            ONET_DIR = onet_dir

        abilities_raw = _load_json("abilities.json")
        work_context_raw = _load_json("work_context.json")
        job_zones_raw = _load_json("job_zones.json")

        # index: soc_code -> {element_name: data_value}, only LV scale rows
        self._abilities = {}
        for row in abilities_raw:
            if row.get(_KEY_SCALE_ID) != "LV":
                continue
            soc = row[_KEY_SOC]
            self._abilities.setdefault(soc, {})[row[_KEY_ELEMENT_NAME]] = float(row[_KEY_DATA_VALUE])

        # index: soc_code -> {element_name: data_value}, CX scale rows
        self._work_context = {}
        for row in work_context_raw:
            if row.get(_KEY_SCALE_ID) != "CX":
                continue
            soc = row[_KEY_SOC]
            self._work_context.setdefault(soc, {})[row[_KEY_ELEMENT_NAME]] = float(row[_KEY_DATA_VALUE])

        # index: soc_code -> job zone (1-5 int)
        self._job_zones = {row[_KEY_SOC]: int(row[_KEY_JOB_ZONE]) for row in job_zones_raw}

        missing = [soc for soc in set(STEP_TO_SOC.values()) if soc not in self._abilities]
        if missing:
            logger.warning(
                f"SOC code(s) {missing} not found in abilities.json - double check STEP_TO_SOC "
                f"and that abilities.json covers these occupations. Falling back to dataset-wide "
                f"mean for any missing code at lookup time."
            )

    def _mean_ability(self, soc: str, element_names: list) -> float:
        scores = self._abilities.get(soc, {})
        values = [scores[e] for e in element_names if e in scores]
        if not values:
            # fallback: average across everything we have for this SOC, else 3.5 (midpoint of 0-7)
            values = list(scores.values()) or [3.5]
        return sum(values) / len(values) / 7.0  # normalize LV 0-7 -> 0-1

    def physical_ability_score(self, step: str) -> float:
        soc = STEP_TO_SOC[step]
        return self._mean_ability(soc, PHYSICAL_ABILITY_ELEMENTS)

    def cognitive_ability_score(self, step: str) -> float:
        soc = STEP_TO_SOC[step]
        return self._mean_ability(soc, COGNITIVE_ABILITY_ELEMENTS)

    def cognitive_focus_score(self, step: str) -> float:
        soc = STEP_TO_SOC[step]
        return self._mean_ability(soc, FOCUS_ABILITY_ELEMENTS)

    def task_complexity_score(self, step: str) -> float:
        """Job Zone (1-5: little/no preparation -> extensive preparation)
        normalized to 0-1."""
        soc = STEP_TO_SOC[step]
        zone = self._job_zones.get(soc, 3)  # default to mid-zone if missing
        return (zone - 1) / 4.0

    def physical_demand_bucket(self, step: str) -> str:
        score = self.physical_ability_score(step)
        if score < 0.4:
            return "low"
        if score < 0.65:
            return "medium"
        return "high"

    def error_severity_bucket(self, step: str) -> str:
        soc = STEP_TO_SOC[step]
        cx = self._work_context.get(soc, {}).get(ERROR_CONTEXT_ELEMENT)
        if cx is None:
            return "moderate"
        # CX scale is 1-5 ("Not serious" -> "Extremely serious")
        if cx < 2.0:
            return "low"
        if cx < 3.25:
            return "moderate"
        if cx < 4.5:
            return "high"
        return "critical"