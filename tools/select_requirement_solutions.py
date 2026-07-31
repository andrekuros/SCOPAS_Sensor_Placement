#!/usr/bin/env python3
"""
Filter Pareto solutions by dual-layer requirements and report the cheapest feasible set.

Example:
  python tools/select_requirement_solutions.py \\
      --results results/demo_targets_coop90_noncoop50/run_targets/ \\
      --min-coop 0.90 --min-noncoop 0.50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

from scopas_metrics import check_dual_layer_requirements


def _load_rows(results: Path):
    for name in ("evaluation_results.json", "pareto_front.json", "pareto_results.json"):
        f = results / name if results.is_dir() else results
        if results.is_dir():
            f = results / name
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data, f
            if isinstance(data, dict) and "pareto_solutions" in data:
                return data["pareto_solutions"], f
    raise FileNotFoundError(f"No evaluation/pareto JSON under {results}")


def main():
    p = argparse.ArgumentParser(description="Select Pareto solutions meeting dual-layer requirements")
    p.add_argument("--results", required=True, help="Results directory or evaluation JSON")
    p.add_argument("--min-coop", type=float, default=None, help="Min M_wp_coop (default: from config or 0.90)")
    p.add_argument("--min-noncoop", type=float, default=None, help="Min M_wp_noncoop (default: from config or 0.50)")
    p.add_argument("--min-fused", type=float, default=None, help="Optional min fused_resilience")
    p.add_argument("--output", default=None, help="Write filtered JSON (default: <results>/requirement_solutions.json)")
    args = p.parse_args()

    results = Path(args.results)
    base = results if results.is_dir() else results.parent
    rows, src = _load_rows(results)

    cfg = {}
    cfg_path = base / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    req = cfg.get("requirements", {})
    min_coop = args.min_coop if args.min_coop is not None else float(req.get("min_M_wp_coop", req.get("min_coverage", 0.90)))
    min_noncoop = args.min_noncoop if args.min_noncoop is not None else float(req.get("min_M_wp_noncoop", 0.50))
    min_fused = args.min_fused if args.min_fused is not None else req.get("min_fused_resilience")

    feasible = []
    for r in rows:
        status = check_dual_layer_requirements(
            r,
            min_M_wp_coop=min_coop,
            min_M_wp_noncoop=min_noncoop,
            min_fused_resilience=min_fused,
        )
        if status["meets_all"]:
            entry = dict(r)
            entry["requirement_check"] = status
            feasible.append(entry)

    feasible.sort(key=lambda r: (r.get("cost", float("inf")), -float(r.get("M_wp_noncoop") or 0)))

    out = Path(args.output) if args.output else base / "requirement_solutions.json"
    summary = {
        "source": str(src),
        "targets": {
            "min_M_wp_coop": min_coop,
            "min_M_wp_noncoop": min_noncoop,
            "min_fused_resilience": min_fused,
        },
        "n_pareto": len(rows),
        "n_feasible": len(feasible),
        "cheapest": None,
        "solutions": feasible,
    }
    if feasible:
        best = feasible[0]
        summary["cheapest"] = {
            "cost": best.get("cost"),
            "M_wp_coop": best.get("M_wp_coop"),
            "M_wp_noncoop": best.get("M_wp_noncoop"),
            "fused_resilience": best.get("fused_resilience"),
            "num_sensors": best.get("num_sensors"),
            "sensors": best.get("sensors") or best.get("sensor_positions"),
        }

    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Targets: M_wp_coop>={min_coop:.0%}  M_wp_noncoop>={min_noncoop:.0%}"
          + (f"  fused>={min_fused:.0%}" if min_fused is not None else ""))
    print(f"Pareto size: {len(rows)}  |  Feasible: {len(feasible)}")
    if not feasible:
        # Helpful nearest misses
        scored = []
        for r in rows:
            coop = float(r.get("M_wp_coop") or 0)
            noncoop = float(r.get("M_wp_noncoop") or 0)
            deficit = max(0.0, min_coop - coop) + max(0.0, min_noncoop - noncoop)
            scored.append((deficit, r))
        scored.sort(key=lambda t: (t[0], t[1].get("cost", 1e18)))
        print("No solution meets both targets. Closest by deficit:")
        for deficit, r in scored[:5]:
            print(
                f"  deficit={deficit:.3f}  coop={float(r.get('M_wp_coop') or 0):.3f}  "
                f"noncoop={float(r.get('M_wp_noncoop') or 0):.3f}  cost=${r.get('cost', 0):,.0f}"
            )
    else:
        c = summary["cheapest"]
        print(
            f"Cheapest feasible: cost=${c['cost']:,.0f}  "
            f"coop={c['M_wp_coop']:.3f}  noncoop={c['M_wp_noncoop']:.3f}  "
            f"sensors={c.get('num_sensors')}"
        )
        if len(feasible) > 1:
            print(f"Also feasible: {len(feasible) - 1} other solution(s) (see {out.name})")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
