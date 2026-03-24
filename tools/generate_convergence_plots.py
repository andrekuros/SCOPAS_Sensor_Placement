#!/usr/bin/env python3
"""
Generate convergence (evolution) plots: objectives over generations.

Sources:
  - evolution_logbook.json in results dir (saved at end of NSGA-II run), or
  - checkpoint .pkl files (--checkpoint-dir + --prefix).

Usage:
  python tools/generate_convergence_plots.py --results results/point_defense_airport_sjc/airport_run_noncoop_only/
  python tools/generate_convergence_plots.py --checkpoint-dir results/.../checkpoints_noncoop --prefix noncoop --output out.png
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import json
import pickle
import numpy as np
import matplotlib.pyplot as plt
import argparse


def load_logbook_from_results(results_dir):
    p = Path(results_dir)
    if not p.is_dir():
        return None
    f = p / "evolution_logbook.json"
    if not f.exists():
        return None
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp)


def load_logbook_from_checkpoints(checkpoint_dir, prefix):
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_files = sorted(checkpoint_path.glob(f"{prefix}_gen*.pkl"))
    if not checkpoint_files:
        return None
    with open(checkpoint_files[-1], "rb") as f:
        data = pickle.load(f)
    return data.get("logbook", [])


def plot_convergence(logbook, output_file, experiment_name, noncoop_only=False):
    if not logbook:
        return
    generations, obj1_avg, obj1_std, obj1_max = [], [], [], []
    obj2_avg, obj2_min = [], []
    for entry in logbook:
        gen = entry.get("generation", 0)
        stats = entry.get("stats", {})
        avg = stats.get("avg", [])
        if not avg:
            continue
        n_obj = len(avg) if hasattr(avg, "__len__") else 0
        if n_obj >= 3:
            generations.append(gen)
            obj1_avg.append(avg[0] * 100)
            obj1_std.append((stats.get("std") or [0, 0, 0])[0] * 100)
            obj1_max.append((stats.get("max") or [0, 0, 0])[0] * 100)
            obj2_avg.append(avg[1])
            obj2_min.append((stats.get("min") or [0, 0, 0])[2] / 1000)
        elif n_obj == 2:
            generations.append(gen)
            obj1_avg.append(avg[0] * 100)
            obj1_std.append((stats.get("std") or [0, 0])[0] * 100)
            obj1_max.append((stats.get("max") or [0, 0])[0] * 100)
            # cost_scaled = cost/100000 -> $K = cost_scaled * 100
            c = (stats.get("min") or [0, 0])[1]
            obj2_min.append(c * 100)
            obj2_avg.append((stats.get("avg") or [0, 0])[1] * 100)
        else:
            continue
    if not generations:
        return
    nobj = len((logbook[0].get("stats") or {}).get("avg", [])) if logbook else 0
    if noncoop_only or nobj == 2:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        ax1, ax2 = axes
        ax1.plot(generations, obj1_avg, "b-", lw=2, label="Mean")
        if obj1_std:
            ax1.fill_between(generations, [a - s for a, s in zip(obj1_avg, obj1_std)], [a + s for a, s in zip(obj1_avg, obj1_std)], alpha=0.2, color="blue")
        if obj1_max:
            ax1.plot(generations, obj1_max, "g--", lw=1, label="Best")
        ax1.set_xlabel("Generation")
        ax1.set_ylabel("M_c noncoop (%)")
        ax1.set_title("Coverage (noncoop) Convergence")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax2.plot(generations, obj2_min if obj2_min else obj2_avg, "g-", lw=2)
        ax2.set_xlabel("Generation")
        ax2.set_ylabel("Cost (scaled $K)")
        ax2.set_title("Cost Evolution")
        ax2.grid(True, alpha=0.3)
    else:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        ax1, ax2, ax3 = axes
        ax1.plot(generations, obj1_avg, "b-", lw=2, label="Mean")
        if obj1_std:
            ax1.fill_between(generations, [a - s for a, s in zip(obj1_avg, obj1_std)], [a + s for a, s in zip(obj1_avg, obj1_std)], alpha=0.2, color="blue")
        if obj1_max:
            ax1.plot(generations, obj1_max, "g--", lw=1, label="Best")
        ax1.set_xlabel("Generation")
        ax1.set_ylabel("Coverage (%)")
        ax1.set_title("Coverage Convergence")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax2.plot(generations, obj2_avg, "r-", lw=2)
        ax2.set_xlabel("Generation")
        ax2.set_ylabel("Redundancy")
        ax2.set_title("Redundancy Convergence")
        ax2.grid(True, alpha=0.3)
        ax3.plot(generations, obj2_min, "g-", lw=2)
        ax3.set_xlabel("Generation")
        ax3.set_ylabel("Cost ($K)")
        ax3.set_title("Cost Evolution")
        ax3.grid(True, alpha=0.3)
    plt.suptitle(f"NSGA-II Convergence: {experiment_name}", fontsize=13, y=1.02)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Saved: {output_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot evolution/convergence from logbook")
    parser.add_argument("--results", type=str, default=None, help="Results dir (looks for evolution_logbook.json)")
    parser.add_argument("--checkpoint-dir", type=str, default=None)
    parser.add_argument("--prefix", type=str, default=None)
    parser.add_argument("--output", type=str, default=None, help="Output PNG (default: <results>/evolution_convergence.png)")
    parser.add_argument("--experiment-name", type=str, default="Experiment")
    parser.add_argument("--noncoop", action="store_true", help="2-objective (M_c noncoop, cost)")
    args = parser.parse_args()

    logbook = None
    out_path = None
    if args.results:
        logbook = load_logbook_from_results(args.results)
        if logbook:
            out_path = Path(args.results) / "evolution_convergence.png"
    if not logbook and args.checkpoint_dir and args.prefix:
        logbook = load_logbook_from_checkpoints(args.checkpoint_dir, args.prefix)
    if args.output:
        out_path = Path(args.output)

    if not logbook:
        print("No logbook found. Use --results <dir> (with evolution_logbook.json) or --checkpoint-dir + --prefix")
        return
    if not out_path:
        out_path = Path("evolution_convergence.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plot_convergence(logbook, str(out_path), args.experiment_name, noncoop_only=args.noncoop)


if __name__ == "__main__":
    main()
