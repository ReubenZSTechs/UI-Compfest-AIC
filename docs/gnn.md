# Factory Placement API — Usage Guide

`factory_placement_API.py` exposes one ready-to-call function, `place_factory()`,
that takes a factory digital-twin JSON (as a Python dict) and returns the
optimal worker → job placement as a JSON-serializable dict. No HTTP server,
no CLI — just a plain Python function.

## Quick start

```python
from training.scripts.factory_placement_API import place_factory

result = place_factory(factory_doc)   # factory_doc = dict matching the factory schema

print(result["optimal_assignment"]["assignments"])
```

That's it. The first call loads the model checkpoint; every call after that
reuses the already-loaded model, so repeated calls are fast.

## `place_factory(factory, weights=None, checkpoint_path=None)`

| Arg | Type | Required | Description |
|---|---|---|---|
| `factory` | `dict` | yes | Factory digital-twin doc — workers, job descriptions, assets, etc. |
| `weights` | `dict` | no | Override how the assignment objective weighs each predicted field. See [Weights](#weights) below. Omit to use defaults. |
| `checkpoint_path` | `str` / `Path` | no | Use a specific model checkpoint instead of the default. Passing a different path than what's cached forces a reload. |

### Return value

```python
{
  "predictions": [
    {
      "worker_id": "...",
      "job_id": "...",
      "job_title": "...",
      "asset_id": "...",
      "overall_compatibility_score": 0.83,
      "throughput_multiplier": 1.12,
      "error_multiplier": 0.95,
      "fatigue_accumulation_rate": 0.04,
      "stress_sensitivity_factor": 0.31
    },
    ...
  ],
  "optimal_assignment": {
    "assignments": [
      {
        "worker_id": "...",
        "job_id": "...",
        "job_title": "...",
        "asset_id": "...",
        "utility": 0.83,
        "overall_compatibility_score": 0.83,
        "throughput_multiplier": 1.12,
        "error_multiplier": 0.95,
        "fatigue_accumulation_rate": 0.04,
        "stress_sensitivity_factor": 0.31
      },
      ...
    ],
    "total_utility": 6.42,
    "unassigned_workers": ["worker_009", "worker_012"],
    "unassigned_jobs": []
  }
}
```

- **`predictions`** — every evaluated (worker, job) pair with the raw model
  output (not filtered to just the chosen assignment).
- **`optimal_assignment.assignments`** — the final worker → job pairing
  chosen by the Hungarian algorithm, sorted best-utility first. Each worker
  and each job appears **at most once**.
- **`unassigned_workers`** / **`unassigned_jobs`** — whichever side has more
  entries (usually workers) will have leftovers here rather than being
  forced into a bad-fit slot.

## Weights

By default, only `overall_compatibility_score` counts toward the assignment
(weight `1.0`), and the other four predicted fields are ignored (weight
`0.0`). To factor more fields into the objective, pass a `weights` dict —
you only need to include the fields you want to change:

```python
result = place_factory(
    factory_doc,
    weights={
        "overall_compatibility_score": 1.0,
        "throughput_multiplier": 0.3,
        "error_multiplier": 0.3,
    },
)
```

Valid field names (same five fields the model predicts):

- `overall_compatibility_score` — higher is better
- `throughput_multiplier` — higher is better
- `error_multiplier` — lower is better
- `fatigue_accumulation_rate` — lower is better
- `stress_sensitivity_factor` — lower is better

You don't need to worry about direction — "lower is better" fields are
automatically inverted internally so every field contributes positively to
the total utility. Passing an unrecognized field name raises a
`ValueError`.

## Using a specific checkpoint

```python
result = place_factory(factory_doc, checkpoint_path="/models/factory_v3.pt")
```

The model is cached per checkpoint path, so switching between a couple of
checkpoints across calls won't cause a reload every time — only when the
path actually changes.

## Calling it many times efficiently (advanced)

`place_factory()` already caches the model in-process, so in most cases you
don't need to do anything extra. If you want explicit control instead
(e.g. managing the model object yourself, or running outside of this
module's cache), use the lower-level functions directly:

```python
from training.scripts.factory_placement_API import load_model_once, predict_and_optimize

model, device = load_model_once()   # load once

for factory_doc in many_factory_docs:
    result = predict_and_optimize(factory_doc, model=model, device=device)
```

## Error handling

`place_factory()` raises `ValueError` if:

- the factory has **zero evaluable (worker, job) pairs** (e.g. no jobs
  resolve to a real `assigned_asset_id`, or `workers` is empty)
- `weights` includes a field name that isn't one of the five valid fields
  listed above

Wrap the call in a `try`/`except ValueError` if the input factory data isn't
guaranteed to already match the expected schema.

## What NOT to use

- `predict_and_optimize()` and `load_model_once()` are still available for
  advanced/manual model management, but `place_factory()` is the intended
  integration point for most use cases — it's the one that's JSON-in,
  JSON-out, with no setup required.