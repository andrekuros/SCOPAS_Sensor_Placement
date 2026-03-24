#!/usr/bin/env python3
"""
Generate 2D and 3D Pareto front plots from saved results (pareto_front.json or evaluation_results.json).
Usage: python tools/plot_pareto_from_results.py --results results/experiment_name/run_id/
"""

import sys
import json
import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def load_objectives(results_path):
    """Load list of (coverage, redundancy, cost) from results file or dir."""
    p = Path(results_path)
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
    else:
        for name in ["evaluation_results.json", "pareto_front.json", "pareto_results.json"]:
            f = p / name
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                break
        else:
            raise FileNotFoundError(f"No results JSON in {p}")
    # Normalize to list of dicts with coverage, redundancy, cost
    if isinstance(data, list):
        rows = data
    else:
        rows = data.get("pareto_solutions", data.get("evaluation_results", []))
    if not rows:
        return [], None
    out = []
    config = data.get("config") if isinstance(data, dict) else None
    use_noncoop = (config or {}).get("optimization", {}).get("objectives") == "noncoop_only"
    for r in rows:
        if use_noncoop:
            cov = r.get("M_wp_noncoop") if r.get("M_wp_noncoop") is not None else r.get("coverage") or r.get("Mc")
        else:
            cov = r.get("coverage") if r.get("coverage") is not None else r.get("Mc")
        red = r.get("redundancy", 0)
        cost = r.get("cost", 0)
        if cov is not None:
            out.append((float(cov) * 100 if cov <= 1 else float(cov), float(red), float(cost)))
    return out, config


def plot_2d_3d(objectives, out_dir, config=None):
    """Write pareto_front.png and pareto_front_3d.png to out_dir."""
    if not objectives:
        print("No objectives to plot")
        return
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    coverages, redundancies, costs = zip(*objectives)
    min_coverage = (config or {}).get("requirements", {}).get("min_coverage")
    min_overlap = (config or {}).get("requirements", {}).get("min_overlap")
    if min_coverage is not None:
        min_coverage = min_coverage * 100

    # 2D: Cost vs Coverage, Cost vs Redundancy
    use_noncoop = (config or {}).get("optimization", {}).get("objectives") == "noncoop_only"
    cov_label = "M_c noncoop (%)" if use_noncoop else "Coverage (%)"
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].scatter(costs, coverages, s=80, alpha=0.7, edgecolors="k")
    axes[0].set_xlabel("Total Cost ($)")
    axes[0].set_ylabel(cov_label)
    axes[0].set_title("Pareto: Cost vs " + ("M_c (noncoop)" if use_noncoop else "Coverage"))
    axes[0].grid(True, alpha=0.3)
    if min_coverage is not None:
        axes[0].axhline(y=min_coverage, color="red", linestyle="--", label=f"Min coverage ({min_coverage:.0f}%)")
        axes[0].legend()
    axes[1].scatter(costs, redundancies, s=80, alpha=0.7, edgecolors="k")
    axes[1].set_xlabel("Total Cost ($)")
    axes[1].set_ylabel("Redundancy")
    axes[1].set_title("Pareto: Cost vs Redundancy")
    axes[1].grid(True, alpha=0.3)
    if min_overlap is not None:
        axes[1].axhline(y=min_overlap, color="red", linestyle="--", label=f"Min overlap ({min_overlap})")
        axes[1].legend()
    plt.tight_layout()
    fig.savefig(out_dir / "pareto_front.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_dir / 'pareto_front.png'}")

    # 3D
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(coverages, redundancies, costs, s=80, alpha=0.7, edgecolors="k")
    ax.set_xlabel(cov_label)
    ax.set_ylabel("Redundancy")
    ax.set_zlabel("Cost ($)")
    ax.set_title("Pareto Front 3D")
    fig.savefig(out_dir / "pareto_front_3d.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_dir / 'pareto_front_3d.png'}")


def main():
    parser = argparse.ArgumentParser(description="Plot 2D/3D Pareto from results")
    parser.add_argument("--results", required=True, help="Results dir or JSON file")
    args = parser.parse_args()
    objectives, config = load_objectives(args.results)
    out_dir = Path(args.results) if Path(args.results).is_dir() else Path(args.results).parent
    plot_2d_3d(objectives, out_dir, config)


if __name__ == "__main__":
    main()
