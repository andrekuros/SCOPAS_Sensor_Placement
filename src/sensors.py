"""
Sensor classes for C-UAS simulation framework
Implements different types of sensors with realistic physical parameters 
constrained for high-density urban environments.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any
import numpy as np


class Sensor(ABC):
    """
    Abstract base class for all sensor types.
    
    Attributes:
        location: (x, y, z) coordinates in meters
        cost: Cost of the sensor
        sensor_type: Type identifier string
        azimuth_deg: Bearing the sensor is pointing (degrees, 0=East, 90=North). Used for FOV when fov_horizontal < 360.
        elevation_min: Minimum elevation angle (degrees)
        elevation_max: Maximum elevation angle (degrees)
        fov_horizontal: Horizontal field of view (degrees)
        max_range: Maximum effective detection range in urban clutter (m)
    """
    
    def __init__(self, location: Tuple[float, float, float], cost: float = 1000.0):
        self.location = location
        self.cost = cost
        self.sensor_type = self._get_sensor_type()
        self.is_active = True
        # Direction the sensor is pointing (degrees). Enables multiple radars at same site with different directions.
        self.azimuth_deg = 0.0
        
        # Default FOV and Range parameters (overridden by subclasses)
        self.elevation_min = -10.0  
        self.elevation_max = 60.0   
        self.fov_horizontal = 360.0  
        self.max_range = 1000.0 
    
    @abstractmethod
    def _get_sensor_type(self) -> str:
        pass
    
    @abstractmethod
    def get_physical_parameters(self) -> Dict[str, Any]:
        pass
    
    def get_distance_to_point(self, point: Tuple[float, float, float]) -> float:
        """Calculate Euclidean distance to a point."""
        return np.sqrt(
            (self.location[0] - point[0])**2 +
            (self.location[1] - point[1])**2 +
            (self.location[2] - point[2])**2
        )


class RadarSensor(Sensor):
    """
    Solid-State / surveillance-class radar model for UAS detection.
    
    Default **horizontal FOV = 360°** (omnidirectional azimuth) as a simplifying
    assumption for example runs and perimeter-style coverage; override
    ``fov_horizontal`` in config for sector panels (e.g. 120°).
    """
    
    def __init__(self, location: Tuple[float, float, float], cost: float = 50000.0):
        super().__init__(location, cost)
        
        # Radar-specific parameters
        self.Pt = 50.0  # Transmit power in Watts (Solid-state ESA)
        self.G = 30.0  # Antenna gain in dB
        self.sigma_RCS = 0.01  # Radar cross section in m² (Small UAV/DJI Phantom)
        self.F = 3.0  # Noise figure in dB
        self.frequency = 2.4e9  # Operating frequency in Hz (2.4 GHz)
        self.bandwidth = 1e6  # Bandwidth in Hz (1 MHz)
        
        self.wavelength = 3e8 / self.frequency  
        
        # Urban FOV & range (config can override; 360° = omni-azimuth scenario)
        self.elevation_min = -5.0   
        self.elevation_max = 30.0   
        self.fov_horizontal = 360.0
        self.max_range = 2000.0  # Default 2 km; config override for 3–5 km typical C-UAS 
    
    def _get_sensor_type(self) -> str:
        return "Radar"
    
    def get_physical_parameters(self) -> Dict[str, Any]:
        return {
            'Pt': self.Pt,
            'G': self.G,
            'sigma_RCS': self.sigma_RCS,
            'F': self.F,
            'frequency': self.frequency,
            'bandwidth': self.bandwidth,
            'wavelength': self.wavelength,
            'max_range': self.max_range
        }


class RFSensor(Sensor):
    """
    Passive RF sensor for UAS communication/RID detection.
    
    Urban Constraints applied:
        - Sensitivity raised to -80 dBm to account for the high 2.4/5.8GHz 
          ISM band noise floor in a dense metropolitan center.
        - Max range effectively capped at 250m due to SINR limits.
    """
    
    def __init__(self, location: Tuple[float, float, float], cost: float = 15000.0):
        super().__init__(location, cost)
        
        # RF-specific parameters
        self.sensitivity = -80.0  # Raised from -90dBm to reflect urban interference temperature
        self.frequency = 2.4e9  # Assuming standard ISM band for drone telemetry
        self.bandwidth = 200e3  # Bandwidth in Hz
        self.antenna_gain = 5.0  # Realistic omni gain in dB
        self.F = 3.0  
        
        # RF FOV & Range
        self.elevation_min = -30.0
        self.elevation_max = 70.0
        self.fov_horizontal = 360.0
        self.max_range = 250.0  # Signal-to-Interference limit
    
    def _get_sensor_type(self) -> str:
        return "RF"
    
    def get_physical_parameters(self) -> Dict[str, Any]:
        return {
            'sensitivity': self.sensitivity,
            'frequency': self.frequency,
            'bandwidth': self.bandwidth,
            'antenna_gain': self.antenna_gain,
            'max_range': self.max_range
        }


class EOSensor(Sensor):
    """
    Electro-Optical sensor for visual UAS classification.
    
    Default **horizontal FOV = 360°** is a coarse notional model (e.g. multi-camera
    site); override ``fov_horizontal`` and ``max_range`` in config for narrow-FOV optics.
    """
    
    def __init__(self, location: Tuple[float, float, float], cost: float = 25000.0):
        super().__init__(location, cost)
        
        # EO-specific parameters
        self.focal_length = 12.0  # Adjusted for wider FOV
        self.sensor_resolution = (3840, 2160)  # 4K resolution required for wide FOV detection
        self.min_target_size = 10  # Minimum pixels to classify
        
        self.elevation_min = -20.0  
        self.elevation_max = 45.0   
        self.fov_horizontal = 360.0
        self.max_range = 150.0
    
    def _get_sensor_type(self) -> str:
        return "EO"
    
    def get_physical_parameters(self) -> Dict[str, Any]:
        return {
            'focal_length': self.focal_length,
            'sensor_resolution': self.sensor_resolution,
            'fov_horizontal': self.fov_horizontal,
            'min_target_size': self.min_target_size,
            'max_range': self.max_range
        }


def create_sensor(sensor_type: str, location: Tuple[float, float, float], cost: float = None) -> Sensor:
    """
    Factory function to create sensors by type.
    Acoustic sensor removed per urban deployment constraints.
    """
    sensor_classes = {
        "Radar": RadarSensor,
        "RF": RFSensor,
        "EO": EOSensor
    }
    
    if sensor_type not in sensor_classes:
        raise ValueError(f"Unknown sensor type: {sensor_type}. Available types: {list(sensor_classes.keys())}")
    
    sensor_class = sensor_classes[sensor_type]
    
    if cost is not None:
        return sensor_class(location, cost)
    else:
        return sensor_class(location)


# Config key -> sensor attribute for create_sensor_from_config overrides
_CONFIG_ATTR_MAP = {
    "cost": "cost",
    "power_W": "Pt",
    "gain_dB": "G",
    "frequency_Hz": "frequency",
    "sigma_RCS": "sigma_RCS",
    "azimuth_deg": "azimuth_deg",
    "elevation_min": "elevation_min",
    "elevation_max": "elevation_max",
    "fov_horizontal": "fov_horizontal",
    "max_range": "max_range",
    "sensitivity_dBm": "sensitivity",
}


def create_sensor_from_config(
    sensor_type: str,
    location: Tuple[float, float, float],
    config: Dict[str, Any],
) -> Sensor:
    """
    Create a sensor from config type and location, applying all config overrides.
    config is the per-type block from config['sensors']['types'][sensor_type].
    """
    type_config = dict(config) if config else {}
    cost = type_config.get("cost", None)
    sensor = create_sensor(sensor_type, location, cost=cost)
    for key, value in type_config.items():
        attr = _CONFIG_ATTR_MAP.get(key)
        if attr is not None and hasattr(sensor, attr):
            setattr(sensor, attr, value)
        elif key in ("cost", "comment"):
            continue
        elif hasattr(sensor, key):
            setattr(sensor, key, value)
    if hasattr(sensor, "frequency") and hasattr(sensor, "wavelength"):
        sensor.wavelength = 3e8 / sensor.frequency
    return sensor