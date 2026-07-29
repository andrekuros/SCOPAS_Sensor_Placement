"""
Deterministic propagation modeling for C-UAS sensor network simulation
Uses ray-tracing on voxelized occupancy grid for PLoS calculation
"""

import numpy as np
import math
from typing import Tuple
from scipy import stats
from skimage.draw import line_nd
from environment import UrbanEnvironment
from sensors import Sensor


def calculate_PLoS_deterministic(point_A: Tuple[float, float, float], 
                                point_B: Tuple[float, float, float], 
                                environment: UrbanEnvironment) -> float:
    """
    Calculate deterministic Probability of Line of Sight (PLoS) using ray-tracing.
    
    Args:
        point_A: First point (x, y, z) in meters
        point_B: Second point (x, y, z) in meters
        environment: Urban environment with voxelized occupancy grid
        
    Returns:
        PLoS probability (0.0 = blocked, 1.0 = clear line of sight)
    """
    x1, y1, z1 = point_A
    x2, y2, z2 = point_B
    
    # Convert world coordinates to voxel indices (plain ints for skimage/numpy compatibility)
    si, sj, sk = environment.world_to_voxel(x1, y1, z1)
    ei, ej, ek = environment.world_to_voxel(x2, y2, z2)
    start_voxel = (int(si), int(sj), int(sk))
    end_voxel = (int(ei), int(ej), int(ek))
    
    # Use skimage.draw.line_nd for ray-tracing
    try:
        # Get all voxel indices along the line
        line_voxels = line_nd(start_voxel, end_voxel, endpoint=True)
        terrain_fn = getattr(environment, 'terrain_height', None)

        # Check if any voxel along the line is occupied (buildings) or below terrain (ground)
        for i in range(len(line_voxels[0])):
            voxel_i = line_voxels[0][i]
            voxel_j = line_voxels[1][i]
            voxel_k = line_voxels[2][i]

            # Check bounds
            if (0 <= voxel_i < environment.grid_shape[0] and
                0 <= voxel_j < environment.grid_shape[1] and
                0 <= voxel_k < environment.grid_shape[2]):

                # Check if voxel is occupied by building
                if environment.occupancy_grid[voxel_i, voxel_j, voxel_k] == 1:
                    return 0.0  # Line of sight blocked

                # Check terrain: if DEM loaded, is voxel center below ground?
                if terrain_fn and callable(terrain_fn):
                    x, y, z = environment.voxel_to_world(voxel_i, voxel_j, voxel_k)
                    ground_z = terrain_fn(x, y)
                    if z < ground_z + 0.5:  # Inside or below terrain
                        return 0.0  # Line of sight blocked by terrain

        return 1.0  # Clear line of sight
        
    except Exception as e:
        # Fallback: simple distance-based calculation
        distance = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
        if distance < 50:  # Very close points
            return 1.0
        else:
            return 0.8  # Conservative estimate


def calculate_PathLoss(distance: float, 
                       frequency: float, 
                       P_LoS: float, 
                       model_name: str = 'COST231-WI') -> float:
    """
    Calculate path loss using deterministic PLoS (0.0 or 1.0).
    
    Args:
        distance: Distance between points in meters
        frequency: Frequency in Hz
        P_LoS: Probability of Line of Sight (0.0 or 1.0 for deterministic)
        model_name: Path loss model name
        
    Returns:
        Path loss in dB
    """
    if distance <= 0:
        return 0.0
    
    # Convert frequency to GHz
    freq_ghz = frequency / 1e9
    
    if model_name == 'FreeSpace':
        # Free space path loss
        path_loss = 20 * math.log10(distance) + 20 * math.log10(freq_ghz) + 32.45
        return path_loss
    
    elif model_name == 'COST231-WI':
        # COST231 Walfish-Ikegami model
        if P_LoS >= 0.5:  # Line of Sight
            # LoS path loss
            path_loss = 32.4 + 20 * math.log10(distance) + 20 * math.log10(freq_ghz)
        else:  # Non-Line of Sight
            # NLoS path loss with building penetration
            path_loss = 32.4 + 20 * math.log10(distance) + 20 * math.log10(freq_ghz) + 20
        
        return path_loss
    
    else:
        # Default model
        path_loss = 20 * math.log10(distance) + 20 * math.log10(freq_ghz) + 32.45
        return path_loss


def get_Noise_RF(environment: UrbanEnvironment) -> float:
    """
    Get RF noise level for the environment.
    
    Args:
        environment: Urban environment
        
    Returns:
        Noise level in dBm
    """
    # Urban RF noise is typically around -90 to -100 dBm
    return -95.0


def get_Noise_Acoustic(environment: UrbanEnvironment) -> float:
    """
    Get acoustic noise level for the environment.
    
    Args:
        environment: Urban environment
        
    Returns:
        Noise level in dB
    """
    # Urban acoustic noise is typically around 60-80 dB
    return 70.0


def calculate_PD_Radar(radar_sensor: Sensor, target_point: Tuple[float, float, float], 
                      environment: UrbanEnvironment) -> float:
    """
    Calculate radar detection probability using deterministic ray-tracing.
    
    Args:
        radar_sensor: Radar sensor instance
        target_point: Target point (x, y, z)
        environment: Urban environment
        
    Returns:
        Detection probability between 0 and 1
    """
    # Get sensor parameters
    Pt = radar_sensor.Pt  # Transmit power (W)
    G = radar_sensor.G    # Antenna gain
    sigma_RCS = radar_sensor.sigma_RCS  # Radar cross section
    F = radar_sensor.F    # Noise figure
    
    # Calculate distance
    distance = radar_sensor.get_distance_to_point(target_point)
    max_range = getattr(radar_sensor, "max_range", 2000.0)
    if distance > max_range:
        return 0.0

    # Calculate deterministic PLoS
    P_LoS = calculate_PLoS_deterministic(radar_sensor.location, target_point, environment)
    
    # Calculate path loss
    frequency = getattr(radar_sensor, 'frequency', 2.4e9)  # Use sensor's configured frequency
    path_loss = calculate_PathLoss(distance, frequency, P_LoS)
    
    # Calculate received power (dBm)
    if distance > 0:
        Pr = 10 * math.log10(Pt * 1000) + G - path_loss + 10 * math.log10(sigma_RCS / (4 * math.pi * distance**2))
    else:
        Pr = 10 * math.log10(Pt * 1000) + G - path_loss  # Very close range
    
    # Calculate noise power (dBm)
    noise_power = get_Noise_RF(environment) + F
    
    # Calculate SNR (dB)
    snr_db = Pr - noise_power
    
    # Convert SNR to linear scale
    snr_linear = 10**(snr_db / 10)
    
    # Calculate detection probability using sigmoid function
    # P_D = 1 / (1 + exp(-k * (SNR - threshold)))
    threshold = 10  # dB threshold for detection
    k = 2  # Steepness parameter
    
    if snr_db > threshold + 10:  # High SNR
        base_pd = 0.95
    elif snr_db < threshold - 10:  # Low SNR
        base_pd = 0.05
    else:
        base_pd = 1 / (1 + math.exp(-k * (snr_db - threshold)))
    
    # CRITICAL: Apply P_LoS as factor (if blocked, P_D should be ~0)
    final_pd = base_pd * P_LoS
    
    return final_pd


def calculate_PD_RF(rf_sensor: Sensor, target_point: Tuple[float, float, float], 
                   environment: UrbanEnvironment, target_power: float = 20.0) -> float:
    """
    Calculate RF detection probability using deterministic ray-tracing.
    
    Args:
        rf_sensor: RF sensor instance
        target_point: Target point (x, y, z)
        environment: Urban environment
        target_power: Target RF power in dBm (típico: 15-20 dBm para drones WiFi/RF)
        
    Returns:
        Detection probability between 0 and 1
    """
    # Calculate distance
    distance = rf_sensor.get_distance_to_point(target_point)
    
    # Calculate deterministic PLoS
    P_LoS = calculate_PLoS_deterministic(rf_sensor.location, target_point, environment)
    
    # Calculate path loss
    frequency = getattr(rf_sensor, 'frequency', 2.4e9)  # Use sensor's configured frequency
    path_loss = calculate_PathLoss(distance, frequency, P_LoS)
    
    # Calculate received power (dBm)
    received_power = target_power - path_loss
    
    # Calculate noise power (dBm)
    noise_power = get_Noise_RF(environment) + rf_sensor.F
    
    # Calculate SNR (dB)
    snr_db = received_power - noise_power
    
    # Calculate detection probability using sigmoid function
    threshold = 5  # dB threshold for RF detection
    k = 1.5  # Steepness parameter
    
    if snr_db > threshold + 5:  # High SNR
        base_pd = 0.9
    elif snr_db < threshold - 5:  # Low SNR
        base_pd = 0.1
    else:
        base_pd = 1 / (1 + math.exp(-k * (snr_db - threshold)))
    
    # CRITICAL: Apply P_LoS as factor (if blocked, P_D should be ~0)
    final_pd = base_pd * P_LoS
    
    return final_pd


def calculate_PD_EO(eo_sensor: Sensor, target_point: Tuple[float, float, float], 
                   environment: UrbanEnvironment) -> float:
    """
    Calculate EO (Electro-Optical) detection probability using deterministic ray-tracing.
    
    Args:
        eo_sensor: EO sensor instance
        target_point: Target point (x, y, z)
        environment: Urban environment
        
    Returns:
        Detection probability between 0 and 1
    """
    # Calculate distance
    distance = eo_sensor.get_distance_to_point(target_point)
    
    # Calculate deterministic PLoS (critical for optical sensors)
    P_LoS = calculate_PLoS_deterministic(eo_sensor.location, target_point, environment)
    
    # EO sensors require clear line of sight
    if P_LoS < 1.0:
        return 0.0  # No detection if line of sight is blocked
    
    # Calculate detection probability based on distance and sensor parameters
    max_range = eo_sensor.max_range
    detection_probability = max(0.0, 1.0 - (distance / max_range)**2)
    
    return detection_probability


def calculate_PD_Acoustic(acoustic_sensor: Sensor, target_point: Tuple[float, float, float],
                         environment: UrbanEnvironment) -> float:
    """
    Acoustic detection probability from source SPL, spherical spreading, absorption,
    urban ambient noise, and soft building occlusion (diffraction-tolerant vs EO).

    Received level (dB SPL) ≈ SL - 20 log10(r) - α·r_km - occlusion_penalty
    SNR = received - ambient; P_D via sigmoid around snr_threshold_dB.
    """
    distance = acoustic_sensor.get_distance_to_point(target_point)
    max_range = getattr(acoustic_sensor, "max_range", 300.0)
    if distance > max_range or distance <= 0:
        return 0.0

    source_spl = getattr(acoustic_sensor, "source_spl_dB", 80.0)
    snr_threshold = getattr(acoustic_sensor, "snr_threshold_dB", 6.0)
    absorption = getattr(acoustic_sensor, "absorption_dB_per_km", 5.0)

    # Spherical spreading + atmospheric absorption
    spreading_db = 20.0 * math.log10(max(distance, 1.0))
    absorption_db = absorption * (distance / 1000.0)
    received_spl = source_spl - spreading_db - absorption_db

    # Soft occlusion: sound can diffract; blocked paths get ~15 dB penalty (not hard zero)
    P_LoS = calculate_PLoS_deterministic(acoustic_sensor.location, target_point, environment)
    if P_LoS < 1.0:
        received_spl -= 15.0

    ambient_db = get_Noise_Acoustic(environment)
    snr_db = received_spl - ambient_db

    # Soft range roll-off near max_range (urban clutter / model bound)
    range_factor = max(0.0, 1.0 - (distance / max_range) ** 2)

    k = 1.2
    if snr_db > snr_threshold + 8:
        base_pd = 0.92
    elif snr_db < snr_threshold - 8:
        base_pd = 0.05
    else:
        base_pd = 1.0 / (1.0 + math.exp(-k * (snr_db - snr_threshold)))

    return float(max(0.0, min(1.0, base_pd * range_factor)))


def check_elevation_angle(sensor: Sensor, target_point: Tuple[float, float, float]) -> bool:
    """
    Check if target is within sensor's elevation angle limits.
    
    Args:
        sensor: Sensor instance
        target_point: Target point (x, y, z)
        
    Returns:
        True if within FOV, False otherwise
    """
    # Calculate elevation angle
    dx = target_point[0] - sensor.location[0]
    dy = target_point[1] - sensor.location[1]
    dz = target_point[2] - sensor.location[2]
    
    distance_xy = math.sqrt(dx**2 + dy**2)
    
    if distance_xy < 0.1:  # Very close horizontally
        if dz > 0:
            elevation = 90.0
        elif dz < 0:
            elevation = -90.0
        else:
            elevation = 0.0
    else:
        elevation = math.degrees(math.atan2(dz, distance_xy))
    
    # Check if within sensor's elevation limits
    elevation_min = getattr(sensor, 'elevation_min', -90.0)
    elevation_max = getattr(sensor, 'elevation_max', 90.0)
    
    if elevation < elevation_min or elevation > elevation_max:
        return False  # Outside FOV
    
    return True


def check_horizontal_fov(sensor: Sensor, target_point: Tuple[float, float, float]) -> bool:
    """
    Check if target is within sensor's horizontal FOV given its azimuth (pointing direction).
    Used for Radar and EO; RF has 360° so always True. Enables multiple radars at same site
    with different directions (e.g. 0°, 120°, 240°).
    
    Args:
        sensor: Sensor instance (uses azimuth_deg, fov_horizontal)
        target_point: Target point (x, y, z)
        
    Returns:
        True if target bearing is within [azimuth - fov/2, azimuth + fov/2]
    """
    fov = getattr(sensor, 'fov_horizontal', 360.0)
    if fov >= 360.0:
        return True
    
    dx = target_point[0] - sensor.location[0]
    dy = target_point[1] - sensor.location[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return True  # Target at sensor location
    
    # Bearing from sensor to target: 0 = East, 90 = North (math.atan2(y,x) gives -180..180)
    bearing_deg = math.degrees(math.atan2(dy, dx))
    bearing_deg = (bearing_deg + 360.0) % 360.0
    
    azimuth = getattr(sensor, 'azimuth_deg', 0.0)
    azimuth = (azimuth + 360.0) % 360.0
    half = fov / 2.0
    low = (azimuth - half + 360.0) % 360.0
    high = (azimuth + half + 360.0) % 360.0
    
    if low <= high:
        return low <= bearing_deg <= high
    # Wrap around 0/360
    return bearing_deg >= low or bearing_deg <= high


def calculate_PD(sensor: Sensor, target_point: Tuple[float, float, float], 
                environment: UrbanEnvironment) -> float:
    """
    Generic function to calculate detection probability for any sensor type.
    Now includes elevation angle check.
    
    Args:
        sensor: Sensor instance
        target_point: Target point (x, y, z)
        environment: Urban environment
        
    Returns:
        Detection probability between 0 and 1
    """
    # Check elevation angle FIRST (quick rejection)
    if not check_elevation_angle(sensor, target_point):
        return 0.0  # Outside sensor's FOV
    # Check horizontal FOV for directional sensors (Radar 120°, EO 90°)
    if not check_horizontal_fov(sensor, target_point):
        return 0.0  # Outside sensor's FOV
    
    sensor_type = sensor.sensor_type
    
    if sensor_type == "Radar":
        return calculate_PD_Radar(sensor, target_point, environment)
    elif sensor_type == "RF":
        return calculate_PD_RF(sensor, target_point, environment)
    elif sensor_type == "EO":
        return calculate_PD_EO(sensor, target_point, environment)
    elif sensor_type == "Acoustic":
        return calculate_PD_Acoustic(sensor, target_point, environment)
    else:
        # Default calculation
        distance = sensor.get_distance_to_point(target_point)
        max_range = getattr(sensor, 'max_range', 1000.0)
        return max(0.0, 1.0 - (distance / max_range))
