# SCOPAS Sensor Types and Configuration

This document describes the sensor types supported by the framework, their parameters, default values, and how JSON config keys map to sensor attributes.

## Supported Types

| Type     | Class          | Layer        | Description                                         |
|----------|----------------|--------------|-----------------------------------------------------|
| Radar    | RadarSensor    | Non-coop     | Solid-state ESA radar for UAS detection             |
| RF       | RFSensor       | Cooperative  | Passive RF for communication / Remote ID detection  |
| EO       | EOSensor       | Non-coop     | Electro-optical for visual classification           |
| Acoustic | AcousticSensor | Non-coop     | Passive mic array for propeller / motor noise        |

Acoustic counts toward **non-cooperative** coverage (`M_wp_noncoop`) because it does not require target RF emissions.

---

## Cost and range comparison (planning defaults)

Defaults are **CapEx planning estimates** for urban sUAS (small electric multi-rotors), not vendor quotes.

| Type     | Default cost (USD) | Urban effective range | Quiet / favorable | Notes |
|----------|--------------------|-----------------------|-------------------|-------|
| Radar    | 50,000             | ~2,000–3,000 m        | similar           | Long-range active; SWaP and clutter sensitivity |
| RF       | 15,000             | ~250 m                | longer if quiet RF| Cooperative only; blind to RF-silent drones |
| EO       | 25,000             | ~150 m                | longer optics     | Needs clear LoS; weather / lighting limited |
| Acoustic | 8,000              | ~300 m                | 200–500 m small quads; km-scale loud ICE | Passive, EW-resilient; urban noise / wind degrade range |

**Acoustic cost rationale**

- Mass / DIY networked nodes (e.g. Sky Fortress / Zvook-class): roughly **USD 400–1,000** hardware.
- Rugged outdoor commercial array + enclosure + edge AI + backhaul (planning node): typically **a few thousand to ~15k**.
- SCOPAS default **USD 8,000** sits in the mid commercial-node band so CapEx trade-offs vs RF/EO remain meaningful without treating DIY BOM as deployable CapEx.

**Acoustic range rationale**

- Vendor / field reports for quiet electric multi-rotors: often **200–500 m** in low ambient noise.
- Dense urban ambient (~70 dB) and wind commonly shorten that; SCOPAS urban default **`max_range = 300 m`**.
- Loud combustion / large fixed-wing drones can be detected at **multi-km** ranges — raise `max_range` and `source_spl_dB` in config for those threat classes.
- Acoustic is best as a **layered** non-coop complement to Radar/EO, not a standalone long-range solution.

---

## Config Key → Sensor Attribute Mapping

When using `create_sensor_from_config(type, location, config)`, the following config keys (in `config['sensors']['types'][type]`) are mapped to sensor attributes:

| Config key            | Sensor attribute      | Applies to      | Unit / notes |
|-----------------------|-----------------------|-----------------|--------------|
| `cost`                | `cost`                | All             | Currency (e.g. USD) |
| `power_W`             | `Pt`                  | Radar           | Watts |
| `gain_dB`             | `G`                   | Radar           | dB |
| `frequency_Hz`        | `frequency`           | Radar, RF       | Hz |
| `sigma_RCS`           | `sigma_RCS`           | Radar           | m² |
| `azimuth_deg`         | `azimuth_deg`         | Radar, EO       | degrees (0=East, 90=North) |
| `elevation_min`       | `elevation_min`       | All             | degrees |
| `elevation_max`       | `elevation_max`       | All             | degrees |
| `fov_horizontal`      | `fov_horizontal`      | All             | degrees |
| `max_range`           | `max_range`           | All             | meters |
| `sensitivity_dBm`     | `sensitivity`         | RF              | dBm |
| `source_spl_dB`       | `source_spl_dB`       | Acoustic        | dB SPL @ 1 m |
| `snr_threshold_dB`    | `snr_threshold_dB`    | Acoustic        | dB above ambient |
| `absorption_dB_per_km`| `absorption_dB_per_km`| Acoustic        | dB/km |

After applying overrides, Radar’s `wavelength` is set from `3e8 / frequency` if both exist. The key `comment` is ignored.

**Multiple radars at same site:** Radars (and EO) can be installed at the same location with different directions. Set `azimuth_deg` per sensor or use the GA’s `orientation_angles_deg` (e.g. `[0, 120, 240]`) so each radar gets an orientation index; propagation enforces horizontal FOV relative to `azimuth_deg`. RF and Acoustic default to 360° and ignore azimuth.

---

## Radar

| Parameter        | Attribute     | Default | Unit   | Description                    |
|------------------|---------------|---------|--------|--------------------------------|
| cost             | cost          | 50000   | —      | Sensor cost                    |
| power_W          | Pt            | 50      | W      | Transmit power                 |
| gain_dB          | G             | 30      | dB     | Antenna gain                   |
| frequency_Hz     | frequency     | 2.4e9   | Hz     | Operating frequency            |
| sigma_RCS        | sigma_RCS     | 0.01    | m²     | Radar cross section (target)   |
| elevation_min    | elevation_min | -5      | °      | Min elevation angle           |
| elevation_max    | elevation_max | 30      | °      | Max elevation angle           |
| fov_horizontal   | fov_horizontal| 360     | °      | Default omni-azimuth; use e.g. 120 in config for sector panel |
| max_range        | max_range     | 2000    | m      | Default max detection range (urban) |
| azimuth_deg      | azimuth_deg   | 0       | °      | Pointing direction (0=East); multiple radars at same site can use 0°, 120°, 240° |

Urban defaults: Pt limited to 50 W, **FOV 360°** (omni-azimuth scenario); override for sector panels. Default max range 2000 m (config can override). With FOV &lt; 360°, multiple radars at the same site can use different directions (e.g. `orientation_angles_deg: [0, 120, 240]` in config).

---

## RF

| Parameter         | Attribute     | Default | Unit   | Description           |
|-------------------|---------------|---------|--------|-----------------------|
| cost              | cost          | 15000   | —      | Sensor cost           |
| sensitivity_dBm   | sensitivity   | -80     | dBm    | Receive sensitivity   |
| frequency_Hz      | frequency     | 2.4e9   | Hz     | Center frequency      |
| elevation_min     | elevation_min | -30     | °      | Min elevation         |
| elevation_max     | elevation_max | 70      | °      | Max elevation         |
| fov_horizontal    | fov_horizontal| 360     | °      | Omnidirectional       |
| max_range         | max_range     | 250     | m      | Max range (SINR)      |

Urban default: sensitivity -80 dBm, max range 250 m.

---

## EO

| Parameter         | Attribute      | Default   | Unit   | Description          |
|-------------------|----------------|-----------|--------|----------------------|
| cost              | cost           | 25000     | —      | Sensor cost          |
| elevation_min     | elevation_min  | -20       | °      | Min elevation         |
| elevation_max     | elevation_max  | 45        | °      | Max elevation         |
| fov_horizontal    | fov_horizontal | 360       | °      | Default omni-azimuth (notional); narrow FOV in config for optics |
| max_range         | max_range      | 150       | m      | Max range (pixels)    |

Urban default: **360°** horizontal FOV in class (simplified); 150 m max range unless overridden.

---

## Acoustic

| Parameter              | Attribute            | Default | Unit     | Description |
|------------------------|----------------------|---------|----------|-------------|
| cost                   | cost                 | 8000    | —        | Networked outdoor array CapEx |
| source_spl_dB          | source_spl_dB        | 80      | dB SPL   | Assumed target source level @ 1 m |
| snr_threshold_dB       | snr_threshold_dB     | 6       | dB       | Detection threshold above ambient |
| absorption_dB_per_km   | absorption_dB_per_km | 5       | dB/km    | Atmospheric absorption |
| elevation_min          | elevation_min        | -20     | °        | Min elevation |
| elevation_max          | elevation_max        | 70      | °        | Max elevation |
| fov_horizontal         | fov_horizontal       | 360     | °        | Omnidirectional array |
| max_range              | max_range            | 300     | m        | Urban small electric sUAS bound |

Detection model (`calculate_PD_Acoustic`): spherical spreading + absorption + ambient noise (~70 dB urban) + soft occlusion penalty (~15 dB when LoS blocked, allowing limited diffraction).

Example config block:

```json
"Acoustic": {
  "cost": 8000.0,
  "source_spl_dB": 80.0,
  "snr_threshold_dB": 6.0,
  "max_range": 300.0,
  "elevation_min": -20.0,
  "elevation_max": 70.0,
  "fov_horizontal": 360.0
}
```

For loud ICE / Shahed-class threats in quieter environments, try `"max_range": 2000` and `"source_spl_dB": 95`.

---

## Propagation and Detection

Detection probability is computed in `src/propagation.py`:

- **Radar**: `calculate_PD_Radar()` — **hard building/terrain LoS gate** (blocked ⇒ \(P_D=0\)), then SNR from power/RCS/range.
- **RF**: `calculate_PD_RF()` (range, sensitivity, LoS).
- **EO**: `calculate_PD_EO()` (range, FOV, **requires clear LoS**).
- **Acoustic**: `calculate_PD_Acoustic()` (SPL, spreading, ambient noise, soft occlusion).

Ray-tracing walks the voxel occupancy grid (`skimage.draw.line_nd`). Coarser `resolution` under-resolves street-canyon shadows; prefer ≤20–30 m for urban radar studies. Buildings shorter than one voxel are not occupied unless you lower `resolution`.

Heatmap tools use `UrbanEnvironment.grid_extent_xy()` (``n * resolution``), not raw scenario bounds max — otherwise coverage cells stretch and no longer line up with building polygons.

See `network_evaluation.py` for network-level coverage (P_Net). Non-cooperative grids include Radar, EO, and Acoustic.

**Visualization note:** `tools/generate_2d_overview.py` plots the LoS-aware \(P_\mathrm{Net}\) heatmap (not raw max-range discs). Optional `--show-max-range` draws dotted nominal-range rings only.
