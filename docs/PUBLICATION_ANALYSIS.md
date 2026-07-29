# SCOPAS Framework — Deep Analysis & Publication Roadmap

**Verdict:** The codebase is a mature research prototype with a clear novel angle beyond the 2023 DASC baseline: dual-layer (coop / non-coop) threat-weighted placement under real urban occlusion and CapEx. A relevant paper is viable if you frame contributions around *methodology + operational evidence*, not around “another NSGA-II wrapper.”

---

## 1. What the framework actually is

SCOPAS optimizes **ground-based heterogeneous sensor networks** (Radar, RF, EO, Acoustic) for sUAS surveillance in 3D urban / airport scenes. It is:

| Layer | Role |
|-------|------|
| Scene | GeoJSON buildings + candidate sites → voxel grid (+ optional DEM) |
| Physics | Ray-traced LoS, FOV/elevation/range gates, per-modality \(P_D\) (incl. Acoustic SNR model) |
| Network | \(P_\mathrm{Net}=1-\prod(1-P_{D,i})\); coop vs non-coop masking |
| Metrics | Classic SCOPAS \(M_c, M_g, C_A\) + point-defense \(M_{wp}\), \(M_{vuln}\), fused resilience, site-aware cost |
| Requirements | Dual-layer floors (`min_M_wp_coop`, `min_M_wp_noncoop`) + Pareto filter tool |
| Search | NSGA-II / NSGA-III (DEAP) with objective profiles `dual_layer` / `coop_only` / `noncoop_only` |
| Evidence | Hypervolume, convergence, flight-level maps, cost-vs-threshold, Cesium/3D export |

**Dual-layer roles (current code):**

- Cooperative \(M_{wp,coop}\): any modality (RF, Radar, EO, Acoustic)
- Non-cooperative \(M_{wp,noncoop}\): Radar, EO, Acoustic (`NONCOOP_SENSOR_TYPES`; RF excluded)

It is positioned as **pre-tactical infrastructure design** (where to sense), complementary to tactical DAA stacks (e.g. DAIDALUS), not a substitute for them.

Sensor CapEx / range defaults and Acoustic rationale: `docs/SENSORS.md`. Demo evidence: `docs/DEMO_RUNS.md`.

---

## 2. Technical depth (strengths)

### 2.1 Solid problem formulation

The decision variables are discrete site/type/(orientation) assignments on real candidate locations. Objectives are operationally meaningful:

- maximize threat-weighted cooperative coverage \(M_{wp,coop}\)
- maximize threat-weighted non-cooperative coverage \(M_{wp,noncoop}\)
- minimize CapEx (hardware + **site activation**)

This matches how airports / C-UAS planners actually argue budgets vs dark-drone risk.

### 2.2 Dual-layer sensing is the real intellectual core

RF covers **cooperative / Remote-ID** targets; Radar / EO / Acoustic cover **dark** targets. Fused resilience measures voxels where **both** layers succeed under the threat map. Empirical runs already show the key research story:

- Coop-only fronts reach high \(M_{wp,coop}\) cheaply (often ≥90% with RF-heavy mixes).
- Non-coop fronts are hard, expensive, and often **fail** high thresholds (≥70%).
- Short target-seeking demos support a practical joint floor near **90% coop / 35% noncoop**; **50% noncoop** with ≥90% coop remains a stretch.

That asymmetry is publishable if treated as a finding, not a bug.

### 2.3 Engineering maturity for a conference paper

Reproducible configs (incl. Acoustic and target-floor demos), split-objective pipeline, requirement filtering (`tools/select_requirement_solutions.py`), hypervolume, OSM/DEM path, external-optimizer API (`evaluate_solution`), and documented case studies (synthetic city + SJC airport) are stronger than many one-off research scripts.

---

## 3. Gaps that weaken a top-tier claim (fix these before claiming novelty)

| Gap | Why it matters for review |
|-----|---------------------------|
| Sensor physics are stylized | Default 360° Radar/EO FOV, simplified \(P_D\), binary LoS — reviewers will ask for fidelity / sensitivity |
| Acoustic model is research-calibrated, not field-validated | SNR / SPL defaults need sensitivity sweeps before strong claims |
| Fusion is coverage-level, not track-level | “Fused resilience” ≠ multi-sensor tracking / association quality |
| Limited algorithm baselines | Mostly NSGA-II vs random; weak vs literature (greedy, MILP approximations, other MOEAs) |
| No measurement validation | No comparison to real radar/RF/acoustic field data or flight-test \(P_D\) |
| Scalability narrative incomplete | Multi-hour city runs; need complexity discussion + ablation on resolution / population |
| Relation to 2023 paper must be crisp | Independent reimplementation + extension — cite clearly; do not overclaim “first SCOPAS” |

---

## 4. What is novel enough to publish (recommended contribution set)

Frame **3–4 crisp contributions**:

1. **Dual-layer multi-objective formulation** for BVLOS / C-UAS sensor placement that separately optimizes cooperative and non-cooperative observability under threat-weighted volumes.
2. **Point-defense metric suite** (\(M_{wp}\), vulnerability, fused resilience, site-activation CapEx / ROI) as an upgrade of classic SCOPAS \(M_c / M_g / C_A\).
3. **Operational evidence** that coop-optimized plans systematically under-protect dark targets; split fronts and joint requirement floors are required for honest safety claims.
4. **Open, reproducible planning toolchain** (GeoJSON scenes, Radar/RF/EO/Acoustic, NSGA-II/III, analysis + requirement filtering) enabling external algorithms via a stable evaluation API.

Optional fifth (only if you strengthen it): coupling SCOPAS outputs as sensing assumptions for tactical DAA (DAIDALUS) — architecture paper angle.

---

## 5. How to work toward a relevant publication

### Phase A — Lock the scientific claim (before more coding)

Write a one-paragraph claim and stick to it, e.g.:

> *Threat-weighted dual-layer Pareto optimization of urban ground-sensor networks reveals a structural trade-off: cooperative coverage is cheap and saturates early, while non-cooperative coverage remains costly and incomplete under realistic occlusion—implying that BVLOS safety cases must report split sensing fronts rather than a single fused score.*

Everything in the paper must serve that claim.

### Phase B — Design the experiment matrix (minimum credible set)

Run and archive **identical seeds / configs** for:

1. **Synthetic city** (`pareto_city_10x10_final`) — controlled urban canyon benchmark.
2. **Airport SJC** (`point_defense_airport_sjc` with `--split-objectives`) — real geometry + assets.
3. **Baselines:** random search + at least one constructive heuristic (e.g. greedy max-marginal \(M_{wp}\)) + NSGA-II; ideally NSGA-III or SPEA2 as second MOEA.
4. **Ablations:** voxel resolution; Radar FOV 360° vs sector (120°); with/without site activation cost; RF present vs Radar+EO(+Acoustic); Acoustic on/off; threat-map on/off.
5. **Requirement corridors:** report cost-to-feasibility for floors such as 90%/35% and stretch 90%/50% (`demo_targets_*` + `select_requirement_solutions.py`).
6. **Reporting:** hypervolume (normalized), attainment surfaces, cost-to-reach threshold curves, flight-level \(M_c\), and **failure to reach** non-coop thresholds (important result).

Do not expand to more scenes until this matrix is clean and reproducible. Short Acoustic/target demos in `docs/DEMO_RUNS.md` are illustrative only — regenerate at paper budget.

### Phase C — Strengthen the method just enough

Prioritize paper-critical upgrades only:

1. **Sensitivity & uncertainty:** sweep sensor params / resolution (incl. Acoustic SPL / SNR); report intervals, not single points.
2. **Directional realism:** sector FOV + orientation genes as default in the airport case (already partially supported).
3. **Complexity / timing table:** voxels × sensors × generations wall-clock.
4. If targeting IEEE Trans / Sensors journal: add a **simple track-continuity proxy** (e.g. contiguous covered voxels along approach corridors) — not full Kalman fusion, but better than binary coverage alone.

Avoid rewriting the stack (REST API, new languages, etc.); it does not buy citations.

### Phase D — Choose venue by contribution shape

| Venue type | Fit | Paper shape |
|------------|-----|-------------|
| **IEEE/AIAA DASC, ICUAS, ICNS** | Best first target | Dual-layer placement + airport case + operational implications |
| **Sensors / Aerospace / Drones (MDPI)** | Good if you add ablations + open data | Method + software + multi-scenario study |
| **IEEE TAES / T-ITS** | Harder | Needs stronger sensing/tracking fidelity or large empirical validation |
| **SoftwareX / JOSS** | Parallel track | Short “framework paper” citing the method paper |

Recommended path: **conference paper first (DASC-class)**, then extended journal with more scenes + baselines.

### Phase E — Paper skeleton (keep it tight)

1. **Intro:** BVLOS needs both coop RID and dark-drone sensing; planners optimize placement under cost.
2. **Related work:** SCOPAS 2023, C-UAS placement, MOO sensor networks, DAA sensing requirements — position as extension, not replacement.
3. **Problem & metrics:** dual-layer formulation, threat map, site CapEx, fused resilience, requirement floors.
4. **Method:** voxel LoS, \(P_D\) models including Acoustic (state assumptions clearly), NSGA-II encoding, objective profiles.
5. **Experiments:** city + SJC; split fronts; Acoustic mix; baselines; ablations; joint floors.
6. **Results:** coop cheap / non-coop hard; cost-threshold curves; hypervolume; maps.
7. **Discussion:** safety-case implications; what SCOPAS does *not* prove (no tactical RWC claim).
8. **Reproducibility:** configs, commands, artifact DOI / repo tag.

### Phase F — Narrative discipline (what to claim / not claim)

**Claim:** planning evidence for sensing infrastructure trade-offs under occlusion and modality asymmetry.  
**Do not claim:** certified DAA performance, weapon-grade tracking, or field-validated \(P_D\) unless you add that evidence.

Use the integration framing already drafted in `docs/SCOPAS_INTEGRATION_TEXT_PACKAGE.md`: SCOPAS = pre-tactical design layer; DAIDALUS/HTLV = tactical RWC.

---

## 6. Suggested near-term work plan (publication-focused)

1. Freeze configs used in the paper; tag a git release (`v0.x-paper`).
2. Re-run city + SJC split with logged seeds; store `evaluation_results.json` + `hypervolume.json` as paper artifacts.
3. Add one greedy baseline script and compare hypervolume / cost-at-threshold.
4. Produce 6–8 publication figures: scene, threat map, Pareto (coop vs noncoop), cost-threshold, flight levels, coverage map comparison, ablation table.
5. Write related-work table differentiating 2023 SCOPAS vs this dual-layer CapEx + Acoustic extension.
6. Submit conference version; keep journal extras (more ablations, second real scene such as Avenida Paulista) for the extension.

---

## 7. Bottom line

SCOPAS is already past “toy code”: it encodes a **relevant BVLOS/C-UAS planning problem** with metrics and case studies that reviewers in avionics / UAS venues will understand. The path to a relevant publication is not more features — it is a **tight claim**, **split-objective evidence**, **honest baselines/ablations**, and **clear limits** relative to tactical DAA and to the 2023 baseline paper.
