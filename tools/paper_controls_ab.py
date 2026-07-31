#!/usr/bin/env python3
"""
Paper strengthening Controls A & B (same ray-tracer / Mc definition).

Control A — small-n oracle:
  Cropped site pools n∈{8,10,12}, deploy exactly k∈{3,4,5} sensors.
  Compare Exhaustive (when tractable), Greedy, Random, NSGA-II (multi-seed).

Control B — matched-budget modality ablation:
  CapEx budgets {31000, 76000, 150000} (hardware only).
  Compare RF-only, Acoustic-only, EO-only, Radar-only, Heterogeneous.

Usage (from repo root):
  python tools/paper_controls_ab.py --out results/paper_controls --resolution 40
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scopas_core import (  # noqa: E402
    load_config,
    load_environment_from_config,
    sensor_list_to_objects,
)
from network_evaluation import NetworkEvaluator  # noqa: E402
from scopas_metrics import calculate_scopas_coverage  # noqa: E402
from sensors import create_sensor_from_config  # noqa: E402

TYPE_ORDER = ["Acoustic", "RF", "EO", "Radar"]
COSTS = {"Acoustic": 8000.0, "RF": 15000.0, "EO": 25000.0, "Radar": 50000.0}
BUDGETS = [31000.0, 76000.0, 150000.0]


def _mc_from_pnet(p_net: np.ndarray, occupied: np.ndarray, threshold: float = 0.8) -> float:
    p = p_net.copy()
    p[occupied == 1] = np.nan
    return float(calculate_scopas_coverage(p, threshold=threshold))


def _fuse(pd_list: Sequence[np.ndarray]) -> np.ndarray:
    if not pd_list:
        raise ValueError("empty")
    out = np.ones_like(pd_list[0], dtype=np.float64)
    for pd in pd_list:
        out *= 1.0 - np.clip(pd, 0.0, 1.0)
    return 1.0 - out


class ControlEngine:
    def __init__(self, config_path: Path, resolution: float, seed: int = 0):
        self.config = load_config(str(config_path))
        self.config["environment"]["resolution"] = float(resolution)
        # Classic Mc path: no critical assets
        self.config.pop("critical_assets", None)
        self.config.pop("site_activation_cost", None)
        self.env = load_environment_from_config(self.config, base_dir=ROOT)
        self.types_cfg = self.config["sensors"]["types"]
        self.locations = self.env.get_sensor_locations()
        self.occupied = self.env.occupancy_grid
        self.evaluator = NetworkEvaluator(self.env)
        self.seed = seed
        self._pd_cache: Dict[Tuple[int, str], np.ndarray] = {}

    def pd_grid(self, site_idx: int, stype: str) -> np.ndarray:
        key = (site_idx, stype)
        if key not in self._pd_cache:
            loc = self.locations[site_idx]
            sensor = create_sensor_from_config(stype, loc, self.types_cfg[stype])
            self._pd_cache[key] = self.evaluator._get_sensor_pd_grid_3d(sensor).astype(np.float64)
        return self._pd_cache[key]

    def mc_for(self, site_idxs: Sequence[int], types: Sequence[str]) -> float:
        grids = [self.pd_grid(i, t) for i, t in zip(site_idxs, types)]
        return _mc_from_pnet(_fuse(grids), self.occupied)

    def cost_for(self, types: Sequence[str]) -> float:
        return float(sum(COSTS[t] for t in types))

    def subsample_sites(self, n: int, seed: Optional[int] = None) -> List[int]:
        rng = random.Random(self.seed if seed is None else seed)
        idxs = list(range(len(self.locations)))
        return sorted(rng.sample(idxs, n))


def exhaustive_best(engine: ControlEngine, pool: List[int], k: int, type_pool: List[str]) -> Dict:
    t0 = time.perf_counter()
    best_mc = -1.0
    best = None
    n_eval = 0
    Cnk = 1
    for i in range(k):
        Cnk = Cnk * (len(pool) - i) // (i + 1)
    type_space = len(type_pool) ** k
    total = Cnk * type_space
    # Full exhaustive if tractable; else site-exhaustive with homogeneous + sampled type mixes
    full = total <= 120_000
    rng = random.Random(engine.seed)
    for sites in itertools.combinations(pool, k):
        if full:
            type_iter = itertools.product(type_pool, repeat=k)
        else:
            mixes = [tuple([t] * k) for t in type_pool]
            for _ in range(min(80, type_space)):
                mixes.append(tuple(rng.choice(type_pool) for _ in range(k)))
            type_iter = dict.fromkeys(mixes)
        for types in type_iter:
            mc = engine.mc_for(sites, types)
            n_eval += 1
            if mc > best_mc:
                best_mc = mc
                best = {
                    "sites": list(sites),
                    "types": list(types),
                    "Mc": mc,
                    "cost": engine.cost_for(types),
                }
    elapsed = time.perf_counter() - t0
    mode = "full_exhaustive" if full else "site_exhaustive_type_sampled"
    return {
        "method": "Exhaustive",
        "mode": mode,
        "Mc": best_mc if best else 0.0,
        "cost": best["cost"] if best else 0.0,
        "types": Counter(best["types"]).most_common() if best else [],
        "n_eval": n_eval,
        "seconds": elapsed,
        "total_space": total,
        "solution": best,
    }


def greedy_best(engine: ControlEngine, pool: List[int], k: int, type_pool: List[str]) -> Dict:
    t0 = time.perf_counter()
    chosen_sites: List[int] = []
    chosen_types: List[str] = []
    remaining = set(pool)
    n_eval = 0
    for _ in range(k):
        best_gain = -1.0
        best_pick = None
        base_mc = engine.mc_for(chosen_sites, chosen_types) if chosen_sites else 0.0
        for s in remaining:
            for t in type_pool:
                mc = engine.mc_for(chosen_sites + [s], chosen_types + [t])
                n_eval += 1
                gain = mc - base_mc
                if gain > best_gain:
                    best_gain = gain
                    best_pick = (s, t, mc)
        if best_pick is None:
            break
        s, t, _ = best_pick
        chosen_sites.append(s)
        chosen_types.append(t)
        remaining.remove(s)
    mc = engine.mc_for(chosen_sites, chosen_types) if chosen_sites else 0.0
    return {
        "method": "Greedy",
        "Mc": mc,
        "cost": engine.cost_for(chosen_types),
        "types": Counter(chosen_types).most_common(),
        "n_eval": n_eval,
        "seconds": time.perf_counter() - t0,
        "solution": {"sites": chosen_sites, "types": chosen_types, "Mc": mc},
    }


def random_best(engine: ControlEngine, pool: List[int], k: int, type_pool: List[str],
                n_samples: int = 200, seeds: Sequence[int] = (0, 1, 2, 3, 4)) -> Dict:
    t0 = time.perf_counter()
    best_mc = -1.0
    best = None
    n_eval = 0
    mcs = []
    for seed in seeds:
        rng = random.Random(seed)
        local_best = -1.0
        for _ in range(n_samples):
            sites = rng.sample(pool, k)
            types = [rng.choice(type_pool) for _ in range(k)]
            mc = engine.mc_for(sites, types)
            n_eval += 1
            if mc > local_best:
                local_best = mc
            if mc > best_mc:
                best_mc = mc
                best = {"sites": sites, "types": types, "Mc": mc, "cost": engine.cost_for(types)}
        mcs.append(local_best)
    return {
        "method": "Random",
        "Mc": best_mc if best else 0.0,
        "Mc_mean": float(np.mean(mcs)) if mcs else 0.0,
        "Mc_std": float(np.std(mcs)) if mcs else 0.0,
        "cost": best["cost"] if best else 0.0,
        "types": Counter(best["types"]).most_common() if best else [],
        "n_eval": n_eval,
        "seconds": time.perf_counter() - t0,
        "n_seeds": len(seeds),
        "samples_per_seed": n_samples,
        "solution": best,
    }


def nsga_best(engine: ControlEngine, pool: List[int], k: int, type_pool: List[str],
              pop: int = 24, gens: int = 15, seeds: Sequence[int] = (0, 1, 2, 3, 4)) -> Dict:
    """Lightweight GA maximizing Mc with fixed k on the site pool (not full DEAP stack)."""
    t0 = time.perf_counter()
    type_idx = {t: i for i, t in enumerate(type_pool)}
    n_eval = 0
    seed_bests = []
    global_best = None
    global_mc = -1.0

    def decode(chrom):
        # chrom: list of (site_pos_in_pool, type_index)
        sites = [pool[c[0]] for c in chrom]
        types = [type_pool[c[1]] for c in chrom]
        return sites, types

    def eval_chrom(chrom):
        nonlocal n_eval
        sites, types = decode(chrom)
        # enforce unique sites
        if len(set(sites)) < k:
            return -1.0
        mc = engine.mc_for(sites, types)
        n_eval += 1
        return mc

    for seed in seeds:
        rng = random.Random(seed)
        # init
        popu = []
        for _ in range(pop):
            site_pos = rng.sample(range(len(pool)), k)
            chrom = [(sp, rng.randrange(len(type_pool))) for sp in site_pos]
            popu.append(chrom)
        fitness = [eval_chrom(c) for c in popu]
        for g in range(gens):
            # tournament + mutate
            new_pop = []
            for _ in range(pop):
                a, b = rng.randrange(pop), rng.randrange(pop)
                parent = popu[a] if fitness[a] >= fitness[b] else popu[b]
                child = [list(g) for g in parent]
                if rng.random() < 0.4:
                    i = rng.randrange(k)
                    child[i][0] = rng.randrange(len(pool))
                if rng.random() < 0.4:
                    i = rng.randrange(k)
                    child[i][1] = rng.randrange(len(type_pool))
                # repair unique sites
                used = set()
                for gene in child:
                    while gene[0] in used:
                        gene[0] = rng.randrange(len(pool))
                    used.add(gene[0])
                new_pop.append([tuple(g) for g in child])
            # elitism
            best_i = int(np.argmax(fitness))
            new_pop[0] = popu[best_i]
            popu = new_pop
            fitness = [eval_chrom(c) for c in popu]
        bi = int(np.argmax(fitness))
        seed_bests.append(fitness[bi])
        if fitness[bi] > global_mc:
            global_mc = fitness[bi]
            sites, types = decode(popu[bi])
            global_best = {"sites": sites, "types": types, "Mc": global_mc, "cost": engine.cost_for(types)}

    return {
        "method": "NSGA-II*",
        "note": "fixed-k Mc-maximizing GA (same ray-tracer); not full multi-objective DEAP",
        "Mc": global_mc if global_best else 0.0,
        "Mc_mean": float(np.mean(seed_bests)) if seed_bests else 0.0,
        "Mc_std": float(np.std(seed_bests)) if seed_bests else 0.0,
        "cost": global_best["cost"] if global_best else 0.0,
        "types": Counter(global_best["types"]).most_common() if global_best else [],
        "n_eval": n_eval,
        "seconds": time.perf_counter() - t0,
        "pop": pop,
        "gens": gens,
        "n_seeds": len(seeds),
        "solution": global_best,
    }


def run_control_a(engine: ControlEngine, pairs: List[Tuple[int, int]]) -> List[Dict]:
    rows = []
    for n, k in pairs:
        pool = engine.subsample_sites(n, seed=engine.seed + n)
        print(f"\n=== Control A: n={n}, k={k}, pool={pool} ===")
        # Warm PD cache for pool × types
        for i in pool:
            for t in TYPE_ORDER:
                engine.pd_grid(i, t)
        exh = exhaustive_best(engine, pool, k, TYPE_ORDER)
        print(f"  Exhaustive Mc={exh['Mc']:.4f}  ({exh['mode']}, {exh['n_eval']} evals, {exh['seconds']:.1f}s)")
        gre = greedy_best(engine, pool, k, TYPE_ORDER)
        print(f"  Greedy     Mc={gre['Mc']:.4f}  ({gre['seconds']:.1f}s)")
        rnd = random_best(engine, pool, k, TYPE_ORDER)
        print(f"  Random     Mc={rnd['Mc']:.4f} mean={rnd['Mc_mean']:.4f}±{rnd['Mc_std']:.4f}")
        nsg = nsga_best(engine, pool, k, TYPE_ORDER)
        print(f"  GA         Mc={nsg['Mc']:.4f} mean={nsg['Mc_mean']:.4f}±{nsg['Mc_std']:.4f}")
        oracle = exh["Mc"]
        row = {
            "n": n,
            "k": k,
            "oracle_Mc": oracle,
            "Exhaustive": exh,
            "Greedy": gre,
            "Random": rnd,
            "NSGA": nsg,
            "delta_Mc": {
                "Greedy": oracle - gre["Mc"],
                "Random": oracle - rnd["Mc"],
                "NSGA": oracle - nsg["Mc"],
            },
            "gap_pct": {
                "Greedy": 100.0 * (1.0 - gre["Mc"] / oracle) if oracle > 1e-9 else None,
                "Random": 100.0 * (1.0 - rnd["Mc"] / oracle) if oracle > 1e-9 else None,
                "NSGA": 100.0 * (1.0 - nsg["Mc"] / oracle) if oracle > 1e-9 else None,
            },
        }
        rows.append(row)
    return rows


def packs_for_budget(budget: float, type_pool: List[str], max_sensors: int = 12) -> List[List[str]]:
    """All multisets of types with hardware cost == budget (exact) or <= budget with max fill."""
    # Prefer exact budget matches used in the paper narrative
    packs = []
    # Exact sum enumerations for small k
    for k in range(1, max_sensors + 1):
        for combo in itertools.combinations_with_replacement(type_pool, k):
            if abs(sum(COSTS[t] for t in combo) - budget) < 0.5:
                packs.append(list(combo))
    # Also near-budget (<= budget, maximize spend within $1k)
    if not packs:
        best = []
        best_spend = -1
        for k in range(1, max_sensors + 1):
            for combo in itertools.combinations_with_replacement(type_pool, k):
                c = sum(COSTS[t] for t in combo)
                if c <= budget + 0.5 and c > best_spend:
                    best_spend = c
                    best = [list(combo)]
                elif abs(c - best_spend) < 0.5 and c <= budget + 0.5:
                    best.append(list(combo))
        packs = best
    # unique
    uniq = []
    seen = set()
    for p in packs:
        key = tuple(sorted(p))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def best_under_packs(engine: ControlEngine, pool: List[int], packs: List[List[str]],
                     site_samples: int = 400, seed: int = 0) -> Dict:
    rng = random.Random(seed)
    best_mc = -1.0
    best = None
    n_eval = 0
    t0 = time.perf_counter()
    for pack in packs:
        k = len(pack)
        if k > len(pool):
            continue
        # enumerate site combos if small, else sample
        C = 1
        for i in range(k):
            C = C * (len(pool) - i) // (i + 1)
        if C <= site_samples:
            site_iter = itertools.combinations(pool, k)
        else:
            site_iter = (tuple(rng.sample(pool, k)) for _ in range(site_samples))
        # type permutations of the pack (distinct assignments to sites)
        type_perms = list(dict.fromkeys(itertools.permutations(pack)))
        for sites in site_iter:
            for types in type_perms:
                mc = engine.mc_for(sites, types)
                n_eval += 1
                if mc > best_mc:
                    best_mc = mc
                    best = {"sites": list(sites), "types": list(types), "Mc": mc, "cost": engine.cost_for(types)}
    return {
        "Mc": best_mc if best else 0.0,
        "cost": best["cost"] if best else 0.0,
        "types": Counter(best["types"]).most_common() if best else [],
        "n_eval": n_eval,
        "seconds": time.perf_counter() - t0,
        "n_packs": len(packs),
        "solution": best,
    }


def run_control_b(engine: ControlEngine, n_pool: int = 40) -> List[Dict]:
    pool = engine.subsample_sites(n_pool, seed=engine.seed + 99)
    print(f"\n=== Control B: site pool n={n_pool} ===")
    for i in pool:
        for t in TYPE_ORDER:
            engine.pd_grid(i, t)
    rows = []
    modalities = {
        "RF-only": ["RF"],
        "Acoustic-only": ["Acoustic"],
        "EO-only": ["EO"],
        "Radar-only": ["Radar"],
        "Heterogeneous": TYPE_ORDER,
    }
    for budget in BUDGETS:
        row = {"budget": budget, "methods": {}}
        print(f"\n-- Budget ${budget:,.0f} --")
        for name, tpool in modalities.items():
            packs = packs_for_budget(budget, tpool)
            if not packs:
                print(f"  {name}: no pack fits budget")
                row["methods"][name] = {"Mc": None, "note": "no_pack"}
                continue
            res = best_under_packs(engine, pool, packs, site_samples=300, seed=engine.seed)
            row["methods"][name] = res
            print(f"  {name}: Mc={res['Mc']:.4f} cost=${res['cost']:,.0f} packs={res['n_packs']} ({res['seconds']:.1f}s)")
        # Winner
        valid = {k: v for k, v in row["methods"].items() if v.get("Mc") is not None}
        if valid:
            winner = max(valid.items(), key=lambda kv: kv[1]["Mc"])
            row["winner"] = winner[0]
            row["hetero_wins"] = winner[0] == "Heterogeneous"
        rows.append(row)
    return rows


def latex_oracle_table(rows: List[Dict]) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Control A — small-$n$ oracle. $\Delta M_c$ = oracle $-$ method (same ray-tracer). NSGA-II* is a fixed-$k$ $M_c$-maximizing GA (5 seeds).}",
        r"\label{tab:oracle_comparison}",
        r"\begin{tabular}{ccrrrrrr}",
        r"\toprule",
        r"$n$ & $k$ & Oracle $M_c$ & Greedy & Random & NSGA-II* & $\Delta_{\mathrm{NSGA}}$ & $t_{\mathrm{oracle}}$ (s) \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(
            f"{r['n']} & {r['k']} & {r['oracle_Mc']*100:.1f}\\% & "
            f"{r['Greedy']['Mc']*100:.1f}\\% & {r['Random']['Mc']*100:.1f}\\% & {r['NSGA']['Mc']*100:.1f}\\% & "
            f"{r['delta_Mc']['NSGA']*100:.1f}\\,pp & {r['Exhaustive']['seconds']:.1f} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def latex_ablation_table(rows: List[Dict]) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Control B — matched CapEx modality ablation (hardware only). Best $M_c$ under each budget.}",
        r"\label{tab:modality_ablation}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Budget & RF-only & Ac-only & EO-only & Radar-only & Heterogeneous \\",
        r"\midrule",
    ]
    for r in rows:
        def fmt(name):
            m = r["methods"].get(name, {})
            if m.get("Mc") is None:
                return "---"
            return f"{m['Mc']*100:.1f}\\%"
        mark = r"\textbf{" + fmt("Heterogeneous") + "}" if r.get("hetero_wins") else fmt("Heterogeneous")
        lines.append(
            f"\\${r['budget']/1000:.0f}k & {fmt('RF-only')} & {fmt('Acoustic-only')} & "
            f"{fmt('EO-only')} & {fmt('Radar-only')} & {mark} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/pareto_city_10x10_final.json")
    ap.add_argument("--resolution", type=float, default=40.0)
    ap.add_argument("--out", default="results/paper_controls")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skip-a", action="store_true")
    ap.add_argument("--skip-b", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading engine (resolution={args.resolution})...")
    engine = ControlEngine(ROOT / args.config, resolution=args.resolution, seed=args.seed)
    print(f"Sites available: {len(engine.locations)}; grid={engine.occupied.shape}")

    # Focused pairs: keep exhaustive tractable; include one larger sampled case
    pairs = [(8, 3), (10, 4), (12, 5)]
    results = {"resolution": args.resolution, "seed": args.seed, "control_a": [], "control_b": []}

    if not args.skip_a:
        results["control_a"] = run_control_a(engine, pairs)
        (out / "control_a.json").write_text(json.dumps(results["control_a"], indent=2) + "\n")
        (out / "tab_oracle_comparison.tex").write_text(latex_oracle_table(results["control_a"]))

    if not args.skip_b:
        results["control_b"] = run_control_b(engine, n_pool=36)
        (out / "control_b.json").write_text(json.dumps(results["control_b"], indent=2) + "\n")
        (out / "tab_modality_ablation.tex").write_text(latex_ablation_table(results["control_b"]))

    (out / "summary.json").write_text(json.dumps({
        "resolution": args.resolution,
        "seed": args.seed,
        "control_a_gaps": [
            {"n": r["n"], "k": r["k"], "gap_NSGA_pp": r["delta_Mc"]["NSGA"] * 100,
             "oracle": r["oracle_Mc"], "nsga": r["NSGA"]["Mc"]}
            for r in results["control_a"]
        ],
        "control_b_winners": [
            {"budget": r["budget"], "winner": r.get("winner"), "hetero_wins": r.get("hetero_wins")}
            for r in results["control_b"]
        ],
    }, indent=2) + "\n")
    print(f"\nWrote results under {out}")


if __name__ == "__main__":
    main()
