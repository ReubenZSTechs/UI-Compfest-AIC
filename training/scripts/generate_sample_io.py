"""
generate_sample_io.py

Generates ONE dummy factory, runs it through factory_placement_API.place_factory(),
and writes out exactly two files so you can open them side by side and eyeball
the shape:

    sample_input_factory.json   <- what a caller sends in
    sample_output_result.json   <- exactly what place_factory() returns

This is deliberately separate from test_factory_placement_api.py (which
checks correctness/invariants). This script's only job is to hand you real
input/output JSON to read - useful for showing your friend the actual
contract before they wire up their integration.

USAGE
    python -m training.scripts.generate_sample_io
    python -m training.scripts.generate_sample_io --factory path/to/factory.json
    python -m training.scripts.generate_sample_io --checkpoint path/to/model.pt
    python -m training.scripts.generate_sample_io --output-dir ./samples/

If --factory is omitted, a synthetic factory is generated on the fly with
generate_synthetic_factories.gen_factory() - no need to have a real factory
JSON on hand.
"""

import argparse
import json
from pathlib import Path


def load_or_generate_factory(factory_path: str | None) -> dict:
    if factory_path:
        return json.loads(Path(factory_path).read_text(encoding="utf-8"))

    from training.scripts.generate_synthetic_factories import gen_factory
    from training.scripts.onet_lookup import OnetProfiles

    onet = OnetProfiles()
    # idx chosen well outside real generation ranges to avoid id collisions
    return gen_factory(idx=9999, onet=onet)


def main():
    parser = argparse.ArgumentParser(
        description="Write one sample input factory JSON and its place_factory() output JSON, for manual inspection."
    )
    parser.add_argument("--factory", default=None, help="Path to a factory JSON to use as input. Omit to auto-generate one.")
    parser.add_argument("--checkpoint", default="./training/datasets/formatted/train/checkpoints/onet_based_cv_folds/fold_4_predictor.pt", help="Optional checkpoint path override.")
    parser.add_argument("--output-dir", default="./training/datasets/formatted/validation/api_test/output/", help="Where to write the two output files. Defaults to current dir.")
    parser.add_argument("--weights", nargs="*", default=None,
                         help="Optional weight overrides, e.g. --weights overall_compatibility_score=1.0 throughput_multiplier=0.3")
    args = parser.parse_args()

    from training.scripts.factory_placement_API import place_factory

    weight_overrides = {}
    for item in args.weights or []:
        field, _, value = item.partition("=")
        weight_overrides[field] = float(value)

    print("Loading/generating sample factory...")
    factory_doc = load_or_generate_factory(args.factory)
    print(f"  {len(factory_doc.get('workers', []))} workers, "
          f"{len(factory_doc.get('job_descriptions', []))} jobs, "
          f"{len(factory_doc.get('assets', []))} assets")

    print("Calling place_factory()...")
    result = place_factory(factory_doc, weights=weight_overrides or None, checkpoint_path=args.checkpoint)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_path = out_dir / "sample_input_factory.json"
    output_path = out_dir / "sample_output_result.json"

    input_path.write_text(json.dumps(factory_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote input  -> {input_path}")
    print(f"Wrote output -> {output_path}")
    print(f"\n{len(result['predictions'])} predictions, "
          f"{len(result['optimal_assignment']['assignments'])} final assignments, "
          f"total_utility={result['optimal_assignment']['total_utility']}")


if __name__ == "__main__":
    main()

    # run: python -m training.scripts.generate_sample_io