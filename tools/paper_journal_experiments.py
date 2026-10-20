#!/usr/bin/env python3
"""Journal-closure experiments for the SCOPAS dual-layer paper.

Subcommands
-----------
airways   E4: evaluate three stored city solutions per airway altitude.
summary   E1/E2: summarize one or more dual-layer fronts (hypervolume, floors).

  python tools/paper_journal_experiments.py airways
  python tools/paper_journal_experiments.py summary --runs results/a results/b --out x.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

PAPER = ROOT / "paper_utm"
CITY_CONFIG = ROOT / "configs" / "paper_rerun_city_dual.json"
CITY_FRONT = PAPER / "results" / "city_dual_evaluation.json"
AIRWAYS = [20.0, 45.0, 65.0]

# Reference point for hypervolume: zero coverage, cost cap in USD.
HV_COST_REF = 700_000.0


def _rows(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("pareto_solutions", data.get("evaluation_results", []))


def _cheapest(rows: List[Dict], coop_min: float, noncoop_min: float) -> Optional[Dict]:
    ok = [r for r in rows if r["M_wp_coop"] >= coop_min and r["M_wp_noncoop"] >= noncoop_min]
    return min(ok, key=lambda r: r["cost"]) if ok else None


def _hv2d(points: List[tuple]) -> float:
    """Area dominated by maximize-maximize points above (0, 0)."""
    pts = sorted(points, key=lambda p: -p[0])
    area, best_y = 0.0, 0.0
    for x, y in pts:
        if y > best_y:
            area += x * (y - best_y)
            best_y = y
    return area


def hypervolume(rows: List[Dict], cost_ref: float = HV_COST_REF) -> float:
    """Exact 3-objective HV: maximize coop, maximize noncoop, minimize cost.

    Normalized so coop, noncoop in [0, 1] and cost in [0, 1] of cost_ref.
    """
    pts = [(r["M_wp_coop"], r["M_wp_noncoop"], r["cost"]) for r in rows if r["cost"] < cost_ref]
    if not pts:
        return 0.0
    pts.sort(key=lambda p: p[2])
    costs = [p[2] for p in pts] + [cost_ref]
    hv = 0.0
    for i in range(len(pts)):
        slab = (costs[i + 1] - costs[i]) / cost_ref
        if slab <= 0:
            continue
        hv += slab * _hv2d([(p[0], p[1]) for p in pts[: i + 1]])
    return hv


def summarize_front(rows: List[Dict]) -> Dict:
    joint = _cheapest(rows, 0.85, 0.35)
    strict = _cheapest(rows, 0.90, 0.35)
    coop90 = _cheapest(rows, 0.90, 0.0)
    return {
        "n_solutions": len(rows),
        "hypervolume": hypervolume(rows),
        "hv_cost_ref_usd": HV_COST_REF,
        "max_coop": max(r["M_wp_coop"] for r in rows),
        "max_noncoop": max(r["M_wp_noncoop"] for r in rows),
        "cheapest_coop90_usd": coop90["cost"] if coop90 else None,
        "noncoop_at_cheapest_coop90": coop90["M_wp_noncoop"] if coop90 else None,
        "cheapest_85_35_usd": joint["cost"] if joint else None,
        "n_feasible_85_35": sum(1 for r in rows if r["M_wp_coop"] >= 0.85 and r["M_wp_noncoop"] >= 0.35),
        "cheapest_90_35_usd": strict["cost"] if strict else None,
    }


def _front_file(run: Path) -> Path:
    if run.is_file():
        return run
    for name in ("evaluation_results.json", "pareto_results.json", "pareto_front.json"):
        if (run / name).exists():
            return run / name
    raise FileNotFoundError(f"no front JSON under {run}")


def cmd_summary(args) -> None:
    out = {"runs": [], "hv_cost_ref_usd": HV_COST_REF}
    for r in args.runs:
        f = _front_file(Path(r))
        s = summarize_front(_rows(f))
        s["source"] = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)
        out["runs"].append(s)
        print(f"{f}: n={s['n_solutions']} HV={s['hypervolume']:.4f} "
              f"85/35=${s['cheapest_85_35_usd']} maxNC={s['max_noncoop']:.3f}")
    keys = ["hypervolume", "max_coop", "max_noncoop", "cheapest_coop90_usd", "cheapest_85_35_usd"]
    agg = {}
    for k in keys:
        vals = [s[k] for s in out["runs"] if s[k] is not None]
        if vals:
            agg[k] = {"min": float(np.min(vals)), "median": float(np.median(vals)),
                      "max": float(np.max(vals)), "n": len(vals)}
    out["aggregate"] = agg
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


def cmd_airways(args) -> None:
    from scopas_core import load_config, load_environment_from_config, sensor_list_to_objects
    from network_evaluation import NetworkEvaluator

    config = load_config(str(CITY_CONFIG))
    env = load_environment_from_config(config, base_dir=ROOT)
    ev = NetworkEvaluator(env)
    rows = _rows(CITY_FRONT)
    picks = {
        "cheap_coop": min((r for r in rows if r["M_wp_coop"] >= 0.80), key=lambda r: r["cost"]),
        "joint_85_35": _cheapest(rows, 0.85, 0.35),
        "best_noncoop": max(rows, key=lambda r: r["M_wp_noncoop"]),
    }
    weights = env.threat_map
    free = env.occupancy_grid == 0
    x0, _, y0, _, z0, _ = env.bounds
    out = {"config": str(CITY_CONFIG.relative_to(ROOT)), "front": str(CITY_FRONT.relative_to(ROOT)),
           "resolution_m": env.voxel_resolution, "airways_m": AIRWAYS, "solutions": {}}
    for name, sol in picks.items():
        sensors = sensor_list_to_objects(sol["sensors"], config["sensors"]["types"])
        coop, noncoop = ev._cooperative_and_noncooperative_grids(sensors)
        per = {}
        for alt in AIRWAYS:
            k = env.world_to_voxel(x0, y0, alt)[2]
            m = free[:, :, k]
            w = weights[:, :, k] * m
            ws = float(np.sum(w))
            zc = float(z0 + (k + 0.5) * env.voxel_resolution)
            per[f"{int(alt)}m"] = {
                "layer_index": int(k),
                "voxel_center_z_m": zc,
                "free_voxels": int(np.sum(m)),
                "M_wp_coop": float(np.sum(coop[:, :, k] * w) / ws) if ws > 0 else 0.0,
                "M_wp_noncoop": float(np.sum(noncoop[:, :, k] * w) / ws) if ws > 0 else 0.0,
                "Mc_coop_uniform": float(np.mean(coop[:, :, k][m] >= 0.8)),
                "Mc_noncoop_uniform": float(np.mean(noncoop[:, :, k][m] >= 0.8)),
            }
        mix: Dict[str, int] = {}
        for s in sol["sensors"]:
            mix[s["type"]] = mix.get(s["type"], 0) + 1
        out["solutions"][name] = {
            "cost_usd": sol["cost"],
            "mix": mix,
            "M_wp_coop_front": sol["M_wp_coop"],
            "M_wp_noncoop_front": sol["M_wp_noncoop"],
            "per_airway": per,
        }
        print(name, sol["cost"], {a: (round(v["M_wp_coop"], 3), round(v["M_wp_noncoop"], 3))
                                  for a, v in per.items()})
    dest = PAPER / "results" / "airways" / "city_airways.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("airways")
    s = sub.add_parser("summary")
    s.add_argument("--runs", nargs="+", required=True)
    s.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "airways":
        cmd_airways(args)
    else:
        cmd_summary(args)


if __name__ == "__main__":
    main()
