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
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def load_objectives(results_path):
    """Load list of objective tuples from results file or dir.

    Returns (points, config, mode) where mode is dual_layer|coop_only|noncoop_only|legacy
    and points are dicts with keys used for plotting.
    """
    p = Path(results_path)
    config = None
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        cfg_path = p.parent / "config.json"
        if cfg_path.exists():
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        for name in ["evaluation_results.json", "pareto_front.json", "pareto_results.json"]:
            f = p / name
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                break
        else:
            raise FileNotFoundError(f"No results JSON in {p}")
        cfg_path = p / "config.json"
        if cfg_path.exists():
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        rows = data
    else:
        rows = data.get("pareto_solutions", data.get("evaluation_results", []))
        if config is None:
            config = data.get("config")
    if not rows:
        return [], config, "legacy"

    mode = (config or {}).get("optimization", {}).get("objectives", "dual_layer")
    # Detect dual-layer metrics even if objectives key missing
    if any(r.get("M_wp_noncoop") is not None for r in rows) and any(r.get("M_wp_coop") is not None for r in rows):
        if mode not in ("coop_only", "noncoop_only"):
            mode = "dual_layer"

    points = []
    for r in rows:
        coop = r.get("M_wp_coop")
        noncoop = r.get("M_wp_noncoop")
        cov = r.get("coverage", r.get("Mc"))
        cost = float(r.get("cost") or 0)
        red = float(r.get("redundancy") or 0)
        points.append({
            "coop": None if coop is None else float(coop) * 100,
            "noncoop": None if noncoop is None else float(noncoop) * 100,
            "coverage": None if cov is None else (float(cov) * 100 if cov <= 1 else float(cov)),
            "redundancy": red,
            "cost": cost,
        })
    return points, config, mode


def plot_2d_3d(points, out_dir, config=None, mode="legacy"):
    """Write pareto_front.png and pareto_front_3d.png to out_dir."""
    if not points:
        print("No objectives to plot")
        return
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    req = (config or {}).get("requirements", {})
    min_coop = req.get("min_M_wp_coop", req.get("min_coverage"))
    min_noncoop = req.get("min_M_wp_noncoop")
    min_coverage = req.get("min_coverage")
    if min_coop is not None:
        min_coop = float(min_coop) * 100
    if min_noncoop is not None:
        min_noncoop = float(min_noncoop) * 100
    if min_coverage is not None:
        min_coverage = float(min_coverage) * 100

    costs = [p["cost"] for p in points]
    if mode == "dual_layer" and all(p["coop"] is not None and p["noncoop"] is not None for p in points):
        coops = [p["coop"] for p in points]
        noncoops = [p["noncoop"] for p in points]
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].scatter(costs, coops, s=80, alpha=0.7, edgecolors="k", c="#2980b9", label="Pareto")
        axes[0].set_xlabel("Total Cost ($)")
        axes[0].set_ylabel("M_wp coop (%)")
        axes[0].set_title("Pareto: Cost vs cooperative protection")
        axes[0].grid(True, alpha=0.3)
        if min_coop is not None:
            axes[0].axhline(y=min_coop, color="red", linestyle="--", label=f"Target coop ≥ {min_coop:.0f}%")
            axes[0].legend()
        axes[1].scatter(costs, noncoops, s=80, alpha=0.7, edgecolors="k", c="#c0392b", label="Pareto")
        axes[1].set_xlabel("Total Cost ($)")
        axes[1].set_ylabel("M_wp noncoop (%)")
        axes[1].set_title("Pareto: Cost vs non-cooperative protection")
        axes[1].grid(True, alpha=0.3)
        if min_noncoop is not None:
            axes[1].axhline(y=min_noncoop, color="red", linestyle="--", label=f"Target noncoop ≥ {min_noncoop:.0f}%")
            axes[1].legend()
        fig.tight_layout()
        fig.savefig(out_dir / "pareto_front.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

        # Requirement box in coop×noncoop space
        fig2, ax = plt.subplots(figsize=(7, 6))
        ax.scatter(coops, noncoops, c=costs, cmap="viridis_r", s=90, edgecolors="k")
        cb = plt.colorbar(ax.collections[0], ax=ax)
        cb.set_label("Cost ($)")
        ax.set_xlabel("M_wp coop (%)")
        ax.set_ylabel("M_wp noncoop (%)")
        ax.set_title("Dual-layer Pareto (color = cost)")
        ax.grid(True, alpha=0.3)
        if min_coop is not None:
            ax.axvline(x=min_coop, color="red", linestyle="--", alpha=0.8)
        if min_noncoop is not None:
            ax.axhline(y=min_noncoop, color="red", linestyle="--", alpha=0.8)
        if min_coop is not None and min_noncoop is not None:
            ax.axhspan(min_noncoop, 100, xmin=min_coop / 100.0, xmax=1.0, color="green", alpha=0.08, label="Feasible region")
            ax.legend(loc="lower right")
        fig2.tight_layout()
        fig2.savefig(out_dir / "pareto_dual_layer_targets.png", dpi=150, bbox_inches="tight")
        plt.close(fig2)

        fig3 = plt.figure(figsize=(8, 6))
        ax3 = fig3.add_subplot(111, projection="3d")
        ax3.scatter(coops, noncoops, costs, s=60, alpha=0.8)
        ax3.set_xlabel("M_wp coop (%)")
        ax3.set_ylabel("M_wp noncoop (%)")
        ax3.set_zlabel("Cost ($)")
        ax3.set_title("3D Pareto: coop × noncoop × cost")
        fig3.tight_layout()
        fig3.savefig(out_dir / "pareto_front_3d.png", dpi=150, bbox_inches="tight")
        plt.close(fig3)
        print(f"Saved: {out_dir / 'pareto_front.png'}")
        print(f"Saved: {out_dir / 'pareto_dual_layer_targets.png'}")
        print(f"Saved: {out_dir / 'pareto_front_3d.png'}")
        return

    # Legacy / single-layer plots
    if mode == "noncoop_only":
        coverages = [p["noncoop"] if p["noncoop"] is not None else p["coverage"] for p in points]
        cov_label = "M_wp noncoop (%)"
    elif mode == "coop_only":
        coverages = [p["coop"] if p["coop"] is not None else p["coverage"] for p in points]
        cov_label = "M_wp coop (%)"
    else:
        coverages = [p["coverage"] for p in points]
        cov_label = "Coverage (%)"
    redundancies = [p["redundancy"] for p in points]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].scatter(costs, coverages, s=80, alpha=0.7, edgecolors="k")
    axes[0].set_xlabel("Total Cost ($)")
    axes[0].set_ylabel(cov_label)
    axes[0].set_title("Pareto: Cost vs " + cov_label)
    axes[0].grid(True, alpha=0.3)
    target = min_noncoop if mode == "noncoop_only" else (min_coop if mode == "coop_only" else min_coverage)
    if target is not None:
        axes[0].axhline(y=target, color="red", linestyle="--", label=f"Target ({target:.0f}%)")
        axes[0].legend()
    axes[1].scatter(costs, redundancies, s=80, alpha=0.7, edgecolors="k")
    axes[1].set_xlabel("Total Cost ($)")
    axes[1].set_ylabel("Redundancy")
    axes[1].set_title("Pareto: Cost vs Redundancy")
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "pareto_front.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig3 = plt.figure(figsize=(8, 6))
    ax3 = fig3.add_subplot(111, projection="3d")
    ax3.scatter(coverages, redundancies, costs, s=60, alpha=0.8)
    ax3.set_xlabel(cov_label)
    ax3.set_ylabel("Redundancy")
    ax3.set_zlabel("Cost ($)")
    ax3.set_title("3D Pareto front")
    fig3.tight_layout()
    fig3.savefig(out_dir / "pareto_front_3d.png", dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print(f"Saved: {out_dir / 'pareto_front.png'}")
    print(f"Saved: {out_dir / 'pareto_front_3d.png'}")


def main():
    parser = argparse.ArgumentParser(description="Plot 2D/3D Pareto from results")
    parser.add_argument("--results", required=True, help="Results dir or JSON file")
    args = parser.parse_args()
    points, config, mode = load_objectives(args.results)
    out_dir = Path(args.results) if Path(args.results).is_dir() else Path(args.results).parent
    plot_2d_3d(points, out_dir, config, mode)


if __name__ == "__main__":
    main()
