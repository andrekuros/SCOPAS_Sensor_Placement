# SCOPAS Sensor Types and Configuration

This document describes the sensor types supported by the framework, their parameters, default values, and how JSON config keys map to sensor attributes.

## Supported Types

| Type  | Class        | Description                                      |
|-------|--------------|--------------------------------------------------|
| Radar | RadarSensor  | Solid-state ESA radar for UAS detection          |
| RF    | RFSensor     | Passive RF for communication/RID detection       |
| EO    | EOSensor     | Electro-optical for visual classification        |

Acoustic sensors are not available in the standard SCOPAS sensor factory/CLI flow.
However, an acoustic propagation path remains in code as an experimental/internal stub.

---

## Config Key → Sensor Attribute Mapping

When using `create_sensor_from_config(type, location, config)`, the following config keys (in `config['sensors']['types'][type]`) are mapped to sensor attributes:

| Config key       | Sensor attribute   | Applies to | Unit / notes        |
|------------------|--------------------|------------|---------------------|
| `cost`           | `cost`             | All        | Currency (e.g. USD) |
| `power_W`        | `Pt`               | Radar      | Watts               |
| `gain_dB`        | `G`                | Radar      | dB                  |
| `frequency_Hz`   | `frequency`        | Radar, RF  | Hz                  |
| `sigma_RCS`      | `sigma_RCS`        | Radar      | m²                  |
| `azimuth_deg`    | `azimuth_deg`      | Radar, EO  | degrees (0=East, 90=North); pointing direction |
| `elevation_min`  | `elevation_min`    | All        | degrees             |
| `elevation_max`  | `elevation_max`    | All        | degrees             |
| `fov_horizontal`| `fov_horizontal`   | All        | degrees             |
| `max_range`      | `max_range`        | All        | meters              |
| `sensitivity_dBm`| `sensitivity`      | RF         | dBm                 |

After applying overrides, Radar’s `wavelength` is set from `3e8 / frequency` if both exist. The key `comment` is ignored.

**Multiple radars at same site:** Radars (and EO) can be installed at the same location with different directions. Set `azimuth_deg` per sensor or use the GA’s `orientation_angles_deg` (e.g. `[0, 120, 240]`) so each radar gets an orientation index; propagation enforces horizontal FOV relative to `azimuth_deg`. RF is 360° and ignores azimuth.

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

## Propagation and Detection

Detection probability is computed in `src/propagation.py`:

- **Radar**: `calculate_PD_Radar()` (range, RCS, LoS/PLoS).
- **RF**: `calculate_PD_RF()` (range, sensitivity, LoS).
- **EO**: `calculate_PD_EO()` (range, FOV, LoS).

See `propagation.py` and `network_evaluation.py` for network-level coverage (P_Net) and redundancy.
