#!/usr/bin/env python3
"""Publication figures for the SCOPAS dual-layer paper.

Reads measured JSON under paper_utm/results and the synthetic-city GeoJSON.
Does not invent metrics. Writes PDF (vector) and PNG (300 dpi).

  python tools/make_journal_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Polygon
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper_utm"
OUT = PAPER / "figures" / "journal"
BUILDINGS = ROOT / "data" / "examples" / "city_10x10_buildings.geojson"
SITES = ROOT / "data" / "examples" / "city_10x10_sensor_locations.geojson"

# Okabe–Ito, print-safe
BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
SKY = "#56B4E9"
PURPLE = "#CC79A7"
YELLOW = "#E69F00"
BLACK = "#222222"
GRAY = "#4D4D4D"


def _style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.linewidth": 0.6,
        "axes.edgecolor": BLACK,
        "axes.labelcolor": BLACK,
        "xtick.color": BLACK,
        "ytick.color": BLACK,
        "text.color": BLACK,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def _save(fig, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {name}")


def _load_rows(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("pareto_solutions", data.get("evaluation_results", []))


def _xy(rows):
    coop = np.array([float(r["M_wp_coop"]) * 100 for r in rows])
    non = np.array([float(r["M_wp_noncoop"]) * 100 for r in rows])
    cost = np.array([float(r["cost"]) / 1000.0 for r in rows])
    return coop, non, cost


def fig_scenario():
    buildings = json.loads(BUILDINGS.read_text(encoding="utf-8"))["features"]
    sites = json.loads(SITES.read_text(encoding="utf-8"))["features"]
    assets = [
        ("Hospital", 500, 500, 120),
        ("Stadium", 250, 750, 100),
        ("Government", 700, 400, 80),
        ("School", 400, 200, 90),
        ("Hub", 150, 500, 100),
    ]
    heights = [float(f["properties"].get("height") or 10) for f in buildings]
    hmin, hmax = min(heights), max(heights)
    cmap = plt.cm.Greys

    fig, ax = plt.subplots(figsize=(7.16, 3.6))
    for feat, h in zip(buildings, heights):
        ring = feat["geometry"]["coordinates"][0]
        t = (h - hmin) / max(hmax - hmin, 1e-6)
        ax.add_patch(Polygon(
            ring, closed=True, facecolor=cmap(0.25 + 0.55 * t),
            edgecolor="#666666", linewidth=0.3, zorder=2,
        ))
    sx, sy = [], []
    for feat in sites:
        x, y = feat["geometry"]["coordinates"][:2]
        sx.append(x)
        sy.append(y)
    ax.scatter(sx, sy, s=4, c=SKY, alpha=0.55, linewidths=0, zorder=3, label="Candidate sites")
    for name, x, y, r in assets:
        ax.add_patch(Circle((x, y), r, fill=False, linestyle="--",
                            edgecolor=ORANGE, linewidth=0.7, zorder=4))
        ax.scatter([x], [y], marker="*", s=46, c=ORANGE, zorder=5, edgecolors=BLACK, linewidths=0.3)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(6, 4),
                    fontsize=6.5, color=BLACK, zorder=6)
    ax.set_xlim(0, 1000)
    ax.set_ylim(0, 1000)
    ax.set_aspect("equal")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_title("Synthetic city, 1 km × 1 km: buildings, candidate sites, and asset radii")
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=SKY, markersize=4, label="Candidate rooftop sites"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor=ORANGE, markeredgecolor=BLACK, markersize=8, label="Critical asset"),
        Line2D([0], [0], color=ORANGE, linestyle="--", linewidth=0.8, label="Protection radius"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=True, fancybox=False,
              edgecolor="#cccccc", framealpha=0.92)
    # height key
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(hmin, hmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Building height (m)")
    cbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    _save(fig, "fig_scenario_city")


def fig_pareto(path: Path = PAPER / "results" / "city_dual_evaluation.json",
               name: str = "fig_city_pareto", non_max: float = 70):
    rows = _load_rows(path)
    coop, non, cost = _xy(rows)
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.15))

    ax = axes[0]
    sc = ax.scatter(cost, coop, c=non, cmap="viridis", s=28, edgecolors=BLACK, linewidths=0.3, zorder=3)
    ax.axhline(90, color=ORANGE, linestyle="--", linewidth=0.8, label="Coop floor 90%")
    ax.set_xlabel("CapEx (thousand USD)")
    ax.set_ylabel(r"Cooperative $M_{wp}$ (%)")
    ax.set_title("(a) Cost versus cooperative coverage")
    ax.set_ylim(0, 105)
    ax.grid(True, linewidth=0.3, color="#dddddd")
    cb = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label(r"Non-cooperative $M_{wp}$ (%)")
    ax.legend(loc="lower right", frameon=False)

    ax = axes[1]
    sc2 = ax.scatter(coop, non, c=cost, cmap="cividis", s=28, edgecolors=BLACK, linewidths=0.3, zorder=3)
    ax.axvline(90, color=ORANGE, linestyle="--", linewidth=0.8)
    ax.axhline(35, color=PURPLE, linestyle="--", linewidth=0.8)
    ax.fill_between([90, 105], 35, 105, color=GREEN, alpha=0.12, zorder=0)
    ax.set_xlim(0, 105)
    ax.set_ylim(0, non_max)
    ax.set_xlabel(r"Cooperative $M_{wp}$ (%)")
    ax.set_ylabel(r"Non-cooperative $M_{wp}$ (%)")
    ax.set_title("(b) Dual-layer trade space")
    ax.grid(True, linewidth=0.3, color="#dddddd")
    ax.text(91, non_max - 3, "90/35\nbox", fontsize=6.5, color=GREEN, va="top")
    cb2 = fig.colorbar(sc2, ax=ax, fraction=0.046, pad=0.03)
    cb2.set_label("CapEx (thousand USD)")
    fig.tight_layout()
    _save(fig, name)


def fig_controls():
    b = json.loads((PAPER / "results" / "controls" / "control_b.json").read_text(encoding="utf-8"))
    c = json.loads((PAPER / "results" / "controls" / "control_c.json").read_text(encoding="utf-8"))
    names = ["RF-only", "Acoustic-only", "EO-only", "Radar-only", "Heterogeneous"]
    short = ["RF", "Acoustic", "EO", "Radar", "Hetero."]
    colors = [BLUE, YELLOW, SKY, PURPLE, ORANGE]

    def series(rows, key):
        budgets, mat = [], []
        for row in rows:
            budgets.append(row["budget"] / 1000.0)
            vals = []
            for n in names:
                m = row["methods"].get(n, {})
                v = m.get(key)
                vals.append(np.nan if v is None else 100.0 * float(v))
            mat.append(vals)
        return np.array(budgets), np.array(mat)

    sites_path = PAPER / "results" / "controls" / "control_c_sites.json"
    s = json.loads(sites_path.read_text(encoding="utf-8")) if sites_path.exists() else None
    panels = [(b, "Mc", r"Best classic $M_c$ (%)", 105, "(a) Control B, classic $M_c$")]
    panels.append((c, "M_wp_noncoop", r"Best $M_{wp,\mathrm{noncoop}}$ (%)", 55,
                   "(b) Control C, hardware only"))
    if s:
        panels.append((s, "M_wp_noncoop", None, 55, "(c) Control C, + \\$15k per site"))
    fig, axes = plt.subplots(1, len(panels), figsize=(7.16, 2.9),
                             gridspec_kw={"width_ratios": [3] + [4] * (len(panels) - 1)})
    width = 0.15
    for pi, (rows, key, ylabel, ymax, title) in enumerate(panels):
        ax = axes[pi]
        xv, mv = series(rows, key)
        idx = np.arange(len(xv))
        for i, (lab, col) in enumerate(zip(short, colors)):
            ax.bar(idx + (i - 2) * width, mv[:, i], width, color=col, edgecolor="none",
                   label=lab if pi == 0 else None)
        ax.set_xticks(idx)
        ax.set_xticklabels([f"{int(v)}k" for v in xv])
        ax.set_xlabel("Budget (USD)")
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.set_ylim(0, ymax)
        ax.set_title(title)
        ax.grid(True, axis="y", linewidth=0.3, color="#dddddd")
    fig.legend(loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    _save(fig, "fig_controls")


def fig_scenes():
    specs = [
        ("Synthetic city", PAPER / "results" / "city_dual_evaluation.json"),
        ("Airport SJC\n(split fronts)", None),
        ("Paulista", PAPER / "results" / "paulista" / "journal.json"),
    ]
    # SJC is two files
    city = _load_rows(specs[0][1])
    paul = _load_rows(specs[2][1])
    coop_sjc = _load_rows(PAPER / "results" / "airport_sjc" / "coop.json")
    non_sjc = _load_rows(PAPER / "results" / "airport_sjc" / "noncoop.json")

    def pack(rows):
        coop, non, cost = _xy(rows)
        return float(np.max(coop)), float(np.max(non))

    labels = ["Synthetic\ncity", "Airport SJC\n(split)", "Paulista\n(30 m)"]
    max_c = [pack(city)[0], pack(coop_sjc)[0], pack(paul)[0]]
    max_n = [pack(city)[1], pack(non_sjc)[1], pack(paul)[1]]

    fig, ax = plt.subplots(figsize=(3.5, 3.1))
    idx = np.arange(3)
    w = 0.36
    ax.bar(idx - w / 2, max_c, w, color=BLUE, label=r"Best $M_{wp,coop}$")
    ax.bar(idx + w / 2, max_n, w, color=ORANGE, label=r"Best $M_{wp,noncoop}$")
    ax.set_xticks(idx)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Best coverage on the front (%)")
    ax.set_ylim(0, 118)
    ax.axhline(90, color=BLUE, linestyle=":", linewidth=0.6)
    ax.axhline(35, color=ORANGE, linestyle=":", linewidth=0.6)
    ax.set_title("Layer asymmetry across scenes")
    ax.legend(frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0))
    ax.grid(True, axis="y", linewidth=0.3, color="#dddddd")
    fig.tight_layout()
    _save(fig, "fig_scenes")


def fig_airways():
    path = PAPER / "results" / "airways" / "city_airways.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    sols = data["solutions"]
    order = [("cheap_coop", BLUE), ("joint_85_35", GREEN), ("best_noncoop", ORANGE)]

    def label(key):
        s = sols[key]
        mix = "+".join(f"{n}{t[:3] if t != 'Acoustic' else 'Ac'}" for t, n in s["mix"].items())
        return f"${s['cost_usd'] / 1000:.0f}k ({mix})"

    alts = data["airways_m"]
    idx = np.arange(len(alts))
    w = 0.26
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.9), sharey=True)
    for ax, key, title in [
        (axes[0], "M_wp_coop", "(a) Cooperative layer"),
        (axes[1], "M_wp_noncoop", "(b) Non-cooperative layer"),
    ]:
        for i, (name, col) in enumerate(order):
            vals = [100 * sols[name]["per_airway"][f"{int(a)}m"][key] for a in alts]
            ax.bar(idx + (i - 1) * w, vals, w, color=col, edgecolor="none",
                   label=label(name) if ax is axes[0] else None)
        ax.set_xticks(idx)
        ax.set_xticklabels([f"{int(a)} m" for a in alts])
        ax.set_xlabel("Airway altitude")
        ax.set_title(title)
        ax.set_ylim(0, 105)
        ax.grid(True, axis="y", linewidth=0.3, color="#dddddd")
    axes[0].set_ylabel(r"Threat-weighted $M_{wp}$ in layer (%)")
    fig.legend(loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    _save(fig, "fig_airways")


def main():
    _style()
    fig_scenario()
    fig_pareto()
    fig_pareto(PAPER / "results" / "paulista" / "journal.json", "fig_paulista_pareto", non_max=40)
    fig_controls()
    fig_scenes()
    fig_airways()


if __name__ == "__main__":
    main()
