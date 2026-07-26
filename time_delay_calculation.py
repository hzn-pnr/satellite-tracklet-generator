"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com

==============================================================================
SCRIPT: SHUTTER DELAY CALCULATION
==============================================================================

DESCRIPTION:
    This script calculates the time bias (shutter delay) using two different
    ephemeris sources for comparison:
    1. SP3 (High Precision): Using Lagrange interpolation on precise orbit files.
    2. TLE (Standard Precision): Using SGP4 propagation via Skyfield.

DATA SOURCE (ASTRIDE):
    The observed RA/DEC coordinates come from Astride line detection results,
    representing the geometric midpoint of the tracklet. Therefore, the script
    aligns calculations to the 'Mid-Exposure Time'.

METHODOLOGY:
    1. INPUTS:
       - SP3 file containing satellite coordinates.
       - Observer's geographic coordinates (Latitude, Longitude, Height).
       - A set of optical observations (UTC Timestamps, RA, DEC). These are taken from ASTRide results.

    2. TIME PREPARATION:
       - The script converts the start time of the observations to 
         "Mid-Exposure Time" (Start Time + Duration / 2).

    3. OPTIMIZATION LOOP:
       - The script defines a 'cost function' that takes a time delay (dt) 
         as input.
       - For a specific delay 'dt', it shifts the observation times.
       - It performs High-Order Lagrange Interpolation (9th degree) on the 
         SP3 data to find the satellite's ITRF position at the shifted times.
       - It converts these ITRF coordinates to Topocentric RA/DEC relative 
         to the observer.
       - It calculates the angular error (residuals) between the 
         Calculated RA/DEC and the Observed RA/DEC using the Great Circle 
         distance formula.

    4. RESULT:
       - The optimizer finds the specific time delay value that minimizes the 
         angular error. This value represents the system's time bias.

==============================================================================
"""

import numpy as np
from scipy.optimize import minimize_scalar
from astropy.time import Time, TimeDelta
from skyfield.api import load, EarthSatellite, wgs84

# IMPORTING CUSTOM MODULES (For SP3)
from sp3_interpolator import interpolate_arbitrary_times_tai, itrf_series_to_topocentric_radec

# ==============================================================================
# 1. COMMON CONFIGURATION (LOCATION & OBSERVATIONS)
# ==============================================================================

# --- OBSERVER LOCATION (Edinburgh) ---
OBS_LAT = 55.923056
OBS_LON = -3.187778
OBS_H_M = 146.0

# --- OBSERVATION DATA (From Astride) ---
# Format: (Year, Month, Day, Hour, Minute, Second) -> UTC Start Time
# ra_obs/dec_obs represent the TRACKLET MIDPOINT.
observations = [
    {
        "t_start": (2025, 5, 5, 1, 36, 44.74), 
        "duration": 5.0,
        "ra_obs": 244.77698014901287, 
        "dec_obs": 47.47727323485372 
    },
    {
        "t_start": (2025, 5, 5, 1, 36, 59.64), 
        "duration": 5.0,
        "ra_obs": 248.89340721514606, 
        "dec_obs": 53.81963286289376
    },
    {
        "t_start": (2025, 5, 5, 1, 37, 14.69), 
        "duration": 5.0,
        "ra_obs": 254.49761156830516, 
        "dec_obs": 59.995382454072136 
    },
]

# ==============================================================================
# 2. SPECIFIC CONFIGURATIONS
# ==============================================================================

# --- SP3 CONFIG ---
SP3_PATH = r"D:\THESIS_CODE\SP3\SWOT\ssaswo20.b25121.e25129.DG_.sp3.001\ssaswo20.b25121.e25129.DG_.sp3.001"
SP3_SAT_ID = "L76"
K_POINTS = 10  # 9th Degree Interpolation

# --- TLE CONFIG ---
# Use the TLE closest to the observation date (2025-05-05)
TLE_LINE1 = "1 54754U 22173A   25124.91307116  .00000058  00000-0  41372-4 0  9996"
TLE_LINE2 = "2 54754  77.6112 226.4321 0000695 268.9472  91.1600 14.00173784122017"
TLE_SAT_NAME = "SWOT_TLE"

# ==============================================================================
# 3. SHARED HELPER FUNCTIONS
# ==============================================================================

def get_mid_times_astropy():
    """Converts observation start times to Astropy Time objects (Mid-Exposure)."""
    mid_times = []
    obs_ra = []
    obs_dec = []
    
    for obs in observations:
        Y, M, D, h, m, s = obs["t_start"]
        t_start = Time(f"{Y}-{M:02d}-{D:02d}T{h:02d}:{m:02d}:{s}", format='isot', scale='utc')
        t_mid = t_start + TimeDelta(obs["duration"] / 2.0, format='sec')
        
        mid_times.append(t_mid)
        obs_ra.append(obs["ra_obs"])
        obs_dec.append(obs["dec_obs"])
        
    return Time(mid_times), np.array(obs_ra), np.array(obs_dec)



def calculate_angular_error_sum(ra_calc_deg, dec_calc_deg, ra_obs_deg, dec_obs_deg):
    """
    Calculates the sum of squared angular errors (in radians) using the 
    Great Circle (Haversine) formula.
    """
    # Convert all inputs to radians
    ra1 = np.radians(ra_calc_deg)
    dec1 = np.radians(dec_calc_deg)
    ra2 = np.radians(ra_obs_deg)
    dec2 = np.radians(dec_obs_deg)
    
    d_ra = ra1 - ra2
    d_dec = dec1 - dec2
    
    # Haversine Formula
#    a = np.sin(d_dec / 2.0)**2 + \
#        np.cos(dec1) * np.cos(dec2) * np.sin(d_ra / 2.0)**2
        
 #   c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

    # Based on Hazan (2026), p. 81, Eq. (4.37)
    c = np.arccos( np.sin(dec1)*np.sin(dec2) + np.cos(dec1)*np.cos(dec2)*np.cos(ra2-ra1) )

    # Return sum of squared errors
    return np.sum(c**2)

# ==============================================================================
# 4. SOLVER: SP3 METHOD
# ==============================================================================
def solve_with_sp3():
    print("\n" + "="*40)
    print("METHOD 1: SP3 (High Precision Ephemeris)")
    print("="*40)
    print(f"File: {SP3_PATH}")
    
    # Get Data
    base_times, obs_ra_arr, obs_dec_arr = get_mid_times_astropy()
    
    def cost_function(delay_sec):
        current_times = base_times + TimeDelta(delay_sec, format='sec')
        
        # Interpolation with Error Handling
        try:
            sat_itrf_km = interpolate_arbitrary_times_tai(
                sp3_path=SP3_PATH,
                target_sat_id=SP3_SAT_ID,
                times_astropy=current_times,
                k_points=K_POINTS, 
                reference="first"
            )
        except Exception:
            return 1e9 # Penalty

        if len(sat_itrf_km) == 0: return 1e9

        # Convert to Topocentric
        topo_coords = itrf_series_to_topocentric_radec(
            sat_xyz_m=sat_itrf_km * 1000.0,
            times=current_times,
            station_lat_deg=OBS_LAT,
            station_lon_deg=OBS_LON,
            station_h_m=OBS_H_M
        )
        
        return calculate_angular_error_sum(
            topo_coords["ra_deg"], topo_coords["dec_deg"],
            obs_ra_arr, obs_dec_arr
        )

    # Optimization
    res = minimize_scalar(cost_function, bounds=(-2.0, 2.0), method='bounded')
    
    if res.success:
        print(f"--> SP3 Calculated Delay: {res.x:.6f} s ({res.x * 1000:.2f} ms)")
    else:
        print("--> SP3 Optimization Failed.")

# ==============================================================================
# 5. SOLVER: TLE METHOD
# ==============================================================================
def solve_with_tle():
    print("\n" + "="*40)
    print("METHOD 2: TLE (SGP4 Propagation)")
    print("="*40)
    print(f"TLE Epoch: Check TLE line 1 for epoch details.")

    # Skyfield Setup
    ts = load.timescale()
    satellite = EarthSatellite(TLE_LINE1, TLE_LINE2, TLE_SAT_NAME, ts)
    observer = wgs84.latlon(OBS_LAT, OBS_LON, elevation_m=OBS_H_M)

    # Prepare Times
    # We use the raw observation list to create Skyfield time objects dynamically
    obs_ra_arr = np.array([o["ra_obs"] for o in observations])
    obs_dec_arr = np.array([o["dec_obs"] for o in observations])
    
    mid_times_raw = []
    for obs in observations:
        Y, M, D, h, m, s = obs["t_start"]
        s_mid = s + (obs["duration"] / 2.0)
        mid_times_raw.append((Y, M, D, h, m, s_mid))

    def cost_function(delay_sec):
        # Create Skyfield Time objects with delay
        t_list = []
        for (Y, M, D, h, m, s_mid) in mid_times_raw:
            t_list.append(ts.utc(Y, M, D, h, m, s_mid + delay_sec))
        
        t_objects = ts.utc([t.utc_datetime() for t in t_list])
        
        # Propagation
        difference = satellite - observer
        topocentric = difference.at(t_objects)
        ra, dec, _ = topocentric.radec()
        
        # Convert Skyfield Angle objects to degrees
        # ra.hours * 15 = degrees
        return calculate_angular_error_sum(
            ra.hours * 15.0, dec.degrees,
            obs_ra_arr, obs_dec_arr
        )

    # Optimization
    res = minimize_scalar(cost_function, bounds=(-2.0, 2.0), method='bounded')
    
    if res.success:
        print(f"--> TLE Calculated Delay: {res.x:.6f} s ({res.x * 1000:.2f} ms)")
    else:
        print("--> TLE Optimization Failed.")

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("Starting Comparison Analysis...")
    
    # Run SP3 Method
    solve_with_sp3()
    
    # Run TLE Method
    solve_with_tle()
    
    print("\n" + "="*40)