#!/usr/bin/env python3
"""
Analyze minimum cost at different coverage levels from Pareto/evaluation results.
Answers: "What is the minimum cost to achieve at least X% coverage?"

Usage:
  python tools/analyze_coverage_levels.py --results results/city_allocation_assets/city_allocation_assets_20260316_003018/
  python tools/analyze_coverage_levels.py --results results/.../ --levels 0.70 0.80 0.90 --output cost_vs_coverage.png
"""

import sys
import json
import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import matplotlib.pyplot as plt


def load_solutions(results_path):
    """Load list of solution dicts (coverage, cost, ...) from results dir or file."""
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
    if isinstance(data, list):
        rows = data
        config = None
        if p.is_dir():
            cfg_file = p / "config.json"
        else:
            cfg_file = p.parent / "config.json"
        if cfg_file.exists():
            config = json.loads(cfg_file.read_text(encoding="utf-8"))
    else:
        rows = data.get("pareto_solutions", data.get("evaluation_results", []))
        config = data.get("config")
    return rows, config


def get_coverage_and_cost(rows, config, use_noncoop=False):
    """Return list of (coverage_frac, cost, num_sensors) per solution."""
    out = []
    for r in rows:
        if use_noncoop:
            cov = r.get("M_wp_noncoop")
        else:
            cov = r.get("M_wp_coop") or r.get("coverage") or r.get("Mc")
        cost = r.get("cost")
        n = r.get("num_sensors", 0)
        if cov is not None and cost is not None:
            c = float(cov) if float(cov) <= 1 else float(cov) / 100.0
            out.append((c, float(cost), int(n)))
    return out


def min_cost_at_levels(data, levels):
    """For each coverage level tau, return min cost among solutions with coverage >= tau."""
    result = []
    for tau in levels:
        feasible = [(cost, n) for c, cost, n in data if c >= tau]
        if feasible:
            cost_min, n_best = min(feasible, key=lambda x: x[0])
            result.append((tau * 100, cost_min, n_best))
        else:
            result.append((tau * 100, None, None))
    return result


def main():
    parser = argparse.ArgumentParser(description="Min cost at different coverage levels")
    parser.add_argument("--results", required=True, help="Results dir or JSON file")
    parser.add_argument("--levels", type=str, default="0.70,0.75,0.80,0.85,0.90,0.95",
                        help="Coverage levels (comma-separated, 0-1)")
    parser.add_argument("--output", default=None, help="Output PNG path")
    parser.add_argument("--dual-layer", action="store_true",
                        help="Report both coop and noncoop (if available)")
    args = parser.parse_args()

    levels = [float(x.strip()) for x in args.levels.split(",") if x.strip()]
    levels = sorted(set(levels))

    rows, config = load_solutions(args.results)
    if not rows:
        print("No solutions found")
        return

    use_noncoop_only = (config or {}).get("optimization", {}).get("objectives") == "noncoop_only"
    out_dir = Path(args.results) if Path(args.results).is_dir() else Path(args.results).parent

    # Coop (or single objective); for noncoop_only use noncoop metric
    data_coop = get_coverage_and_cost(rows, config, use_noncoop=use_noncoop_only)
    cov_label = "M_wp_noncoop" if use_noncoop_only else "M_wp_coop"
    if data_coop:
        table_coop = min_cost_at_levels(data_coop, levels)
        print(f"Coverage level ({cov_label}) – minimum cost")
        print("-" * 50)
        for pct, cost, n in table_coop:
            if cost is not None:
                print(f"  {pct:.0f}%  ->  ${cost:,.0f}  ({n} sensors)")
            else:
                print(f"  {pct:.0f}%  ->  (no solution)")

    # Noncoop (if dual-layer and not noncoop_only)
    if args.dual_layer and not use_noncoop_only:
        data_noncoop = get_coverage_and_cost(rows, config, use_noncoop=True)
        if data_noncoop:
            table_noncoop = min_cost_at_levels(data_noncoop, levels)
            print("\nCoverage level (noncoop / M_wp_noncoop) – minimum cost")
            print("-" * 50)
            for pct, cost, n in table_noncoop:
                if cost is not None:
                    print(f"  {pct:.0f}%  ->  ${cost:,.0f}  ({n} sensors)")
                else:
                    print(f"  {pct:.0f}%  ->  (no solution)")

    # Plot: min cost vs required coverage
    if data_coop:
        table = min_cost_at_levels(data_coop, levels)
        x = [t[0] for t in table]
        y = [t[1] if t[1] is not None else float("nan") for t in table]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(x, y, "o-", linewidth=2, markersize=8, color="C0", label=f"Min cost ({cov_label})")
        ax.set_xlabel("Required coverage (%)")
        ax.set_ylabel("Minimum cost ($)")
        ax.set_title("Cost vs coverage level (solutions with coverage ≥ τ)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        if args.dual_layer and not use_noncoop_only and data_noncoop:
            table_n = min_cost_at_levels(data_noncoop, levels)
            yn = [t[1] if t[1] is not None else float("nan") for t in table_n]
            ax.plot(x, yn, "s--", linewidth=1.5, markersize=6, color="C1", label="Min cost (noncoop)")
            ax.legend()
        plt.tight_layout()
        out_file = Path(args.output) if args.output else out_dir / "cost_vs_coverage_level.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_file, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
