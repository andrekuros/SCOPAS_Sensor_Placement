"""
Evaluate a user-defined sensor deployment against a SCOPAS config.

This script shows how researchers can:
1. Define a sensor deployment by hand (or load from their own optimizer),
2. Evaluate it using the full SCOPAS metric suite (M_wp_coop, M_wp_noncoop,
   fused_resilience, cost, asset_security_roi, etc.),
3. Save results to a JSON file for further analysis.

Run from the project root:

    python examples/evaluate_custom_solution.py --config configs/city_allocation_assets.json

To evaluate your own solutions via the CLI instead of Python, use:

    python run_framework.py --config configs/city_allocation_assets.json --mode evaluate \\
        --solutions-file my_solutions.json --output my_results.json

Where my_solutions.json is a list of deployments:

    [
      [
        {"type": "Radar", "x": 500, "y": 500, "z": 30},
        {"type": "RF", "x": 200, "y": 700, "z": 25}
      ]
    ]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scopas_core import load_config, load_environment_from_config, evaluate_solution


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate a custom sensor deployment")
    parser.add_argument("--config", default="configs/city_allocation_assets.json",
                        help="SCOPAS JSON config")
    parser.add_argument("--output", default=None, help="Save results to JSON file")
    args = parser.parse_args()

    config = load_config(str(ROOT / args.config))
    env = load_environment_from_config(config, base_dir=ROOT)
    sensor_types = config.get("sensors", {}).get("types", {})

    # --- Define your deployment here ---
    my_solution = [
        {"type": "Radar", "x": 500, "y": 500, "z": 30},
        {"type": "Radar", "x": 200, "y": 800, "z": 25},
        {"type": "RF",    "x": 700, "y": 400, "z": 35},
        {"type": "RF",    "x": 300, "y": 200, "z": 20},
        {"type": "EO",    "x": 150, "y": 550, "z": 25},
    ]

    print(f"Config: {args.config}")
    print(f"Sensors: {len(my_solution)} ({', '.join(s['type'] for s in my_solution)})")
    print()

    results = evaluate_solution(env, my_solution, sensor_types, config=config)

    for key in ["M_wp_coop", "M_wp_noncoop", "M_vuln_coop", "M_vuln_noncoop",
                "fused_resilience", "asset_security_roi", "cost", "num_sensors", "unique_sites"]:
        val = results.get(key)
        if val is not None:
            if isinstance(val, float) and val < 10:
                print(f"  {key:30s} = {val:.4f}")
            else:
                print(f"  {key:30s} = {val:,.2f}" if isinstance(val, float) else f"  {key:30s} = {val}")

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
